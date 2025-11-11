from flask import Flask, render_template, jsonify, request
from flask_cors import CORS
from drug_search import load_drug_data_api, find_identical_ingredients, KEY
import pandas as pd
import requests
import xml.etree.ElementTree as ET
from typing import Optional, Dict, List
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

app = Flask(__name__)
CORS(app)

# 전역 변수로 데이터프레임 캐싱
cached_df: Optional[pd.DataFrame] = None

@app.route('/')
def index():
    """메인 페이지"""
    return render_template('index.html')

@app.route('/api/search', methods=['POST'])
def search_drug():
    """의약품 검색 API"""
    try:
        data = request.json
        gnlNmCd = data.get('gnlNmCd')
        itmNm = data.get('itmNm')
        mdsCd = data.get('mdsCd')
        mnfEntpNm = data.get('mnfEntpNm')
        num_rows = data.get('num_rows', 20)
        
        # 검색 조건 확인
        if not any([gnlNmCd, itmNm, mdsCd, mnfEntpNm]):
            return jsonify({
                'success': False,
                'error': '최소 하나의 검색 조건을 입력해주세요.'
            }), 400
        
        # 성분코드가 포함된 경우 처리
        if gnlNmCd:
            # 성분코드로 동일성분 의약품 검색
            global cached_df
            
            # 캐시된 데이터가 없으면 로드
            if cached_df is None:
                cached_df = load_drug_data_api()
            
            if cached_df is None or cached_df.empty:
                return jsonify({
                    'success': False,
                    'error': '의약품 데이터를 로드할 수 없습니다.'
                }), 500
            
            # 동일성분 의약품 찾기
            identical = find_identical_ingredients(gnlNmCd, cached_df)
            
            if identical.empty:
                return jsonify({
                    'success': True,
                    'isIdenticalSearch': False,
                    'results': []
                })
            
            # 다른 조건이 있으면 필터링
            if any([itmNm, mdsCd, mnfEntpNm]):
                # 제품코드로 필터링
                if mdsCd:
                    mds_cd_col = None
                    for col in identical.columns:
                        if '제품코드' in col or 'mdsCd' in col or col == 'mdsCd':
                            mds_cd_col = col
                            break
                    if mds_cd_col:
                        identical = identical[identical[mds_cd_col] == mdsCd]
                
                # 제조업체명으로 필터링
                if mnfEntpNm:
                    mnf_col = None
                    for col in identical.columns:
                        if '제조업체' in col or 'mnfEntpNm' in col or '제조업체명' in col:
                            mnf_col = col
                            break
                    if mnf_col:
                        identical = identical[identical[mnf_col].str.contains(mnfEntpNm, na=False, case=False)]
                
                # 품목명으로 필터링
                if itmNm:
                    item_name_col = None
                    for col in identical.columns:
                        if '품목명' in col or '제품명' in col or col == 'itmNm':
                            item_name_col = col
                            break
                    if item_name_col:
                        identical = identical[identical[item_name_col].str.contains(itmNm, na=False, case=False)]
            
            if identical.empty:
                return jsonify({
                    'success': True,
                    'isIdenticalSearch': False,
                    'results': []
                })
            
            # 품목명 컬럼 찾기
            item_name_col = None
            for col in identical.columns:
                if '품목명' in col or '제품명' in col or col == 'itmNm' or col == '품목명':
                    item_name_col = col
                    break
            
            if item_name_col is None:
                # 품목명 컬럼을 찾을 수 없으면 직접 결과 반환
                results = identical.to_dict('records')
                return jsonify({
                    'success': True,
                    'isIdenticalSearch': False,
                    'results': results
                })
            
            # 품목명 리스트 추출 (중복 제거)
            item_names = identical[item_name_col].dropna().unique().tolist()
            
            if not item_names:
                return jsonify({
                    'success': True,
                    'isIdenticalSearch': False,
                    'results': []
                })
            
            # 각 품목명으로 일반 검색 수행
            all_results = []
            seen_items = set()  # 중복 제거용
            
            for item_name in item_names[:50]:  # 최대 50개까지만 검색
                if not item_name or pd.isna(item_name):
                    continue
                
                # 품목명으로 검색하되, 다른 조건도 함께 전달
                search_results = get_detailed_search_results(
                    itmNm=str(item_name),
                    mdsCd=mdsCd if mdsCd else None,
                    mnfEntpNm=mnfEntpNm if mnfEntpNm else None,
                    num_rows=100  # 각 품목명당 최대 100개
                )
                
                # 결과 필터링 (제조업체명, 제품코드)
                for result in search_results:
                    mds_cd = result.get('mdsCd')
                    if mds_cd and mds_cd not in seen_items:
                        # 제조업체명 필터링
                        if mnfEntpNm:
                            mnf_result = result.get('mnfEntpNm', '')
                            if mnfEntpNm.lower() not in str(mnf_result).lower():
                                continue
                        
                        # 제품코드 필터링
                        if mdsCd and result.get('mdsCd') != mdsCd:
                            continue
                        
                        seen_items.add(mds_cd)
                        all_results.append(result)
            
            return jsonify({
                'success': True,
                'isIdenticalSearch': False,  # 일반 검색 결과로 표시
                'results': all_results
            })
        
        # 성분코드 없이 다른 조건만 입력된 경우 일반 검색
        search_results = get_detailed_search_results(
            gnlNmCd=None,
            itmNm=itmNm,
            mdsCd=mdsCd,
            mnfEntpNm=mnfEntpNm,
            num_rows=num_rows
        )
        
        return jsonify({
            'success': True,
            'isIdenticalSearch': False,  # 일반 검색임을 표시
            'results': search_results if search_results else []
        })
    except Exception as e:
        print(f"검색 API 오류: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/identical', methods=['POST'])
def get_identical_drugs():
    """동일성분 의약품 검색 API"""
    try:
        data = request.json
        gnlNmCd = data.get('gnlNmCd')
        
        if not gnlNmCd:
            return jsonify({
                'success': False,
                'error': '성분코드가 필요합니다.'
            }), 400
        
        global cached_df
        
        # 캐시된 데이터가 없으면 로드
        if cached_df is None:
            cached_df = load_drug_data_api()
        
        if cached_df is None or cached_df.empty:
            return jsonify({
                'success': False,
                'error': '의약품 데이터를 로드할 수 없습니다.'
            }), 500
        
        # 동일성분 의약품 찾기
        identical = find_identical_ingredients(gnlNmCd, cached_df)
        
        # DataFrame을 JSON으로 변환
        if not identical.empty:
            results = identical.to_dict('records')
            return jsonify({
                'success': True,
                'count': len(results),
                'results': results
            })
        else:
            return jsonify({
                'success': True,
                'count': 0,
                'results': []
            })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

def get_detailed_search_results(
    gnlNmCd: Optional[str] = None,
    itmNm: Optional[str] = None,
    mdsCd: Optional[str] = None,
    mnfEntpNm: Optional[str] = None,
    num_rows: int = 20
) -> List[Dict]:
    """상세 검색 결과 반환 (페이지네이션 지원)"""
    endpoint = "https://apis.data.go.kr/B551182/dgamtCrtrInfoService1.2/getDgamtList"
    
    search_params = {}
    if gnlNmCd:
        search_params["gnlNmCd"] = gnlNmCd
    if itmNm:
        search_params["itmNm"] = itmNm
    if mdsCd:
        search_params["mdsCd"] = mdsCd
    if mnfEntpNm:
        search_params["mnfEntpNm"] = mnfEntpNm
    
    all_results = []
    page = 1
    total_count = 0
    
    while True:
        params = {
            "ServiceKey": KEY,
            "numOfRows": str(num_rows),
            "pageNo": str(page)
        }
        params.update(search_params)
        
        try:
            response = requests.get(endpoint, params=params, verify=False, timeout=30)
            
            if response.status_code != 200:
                print(f"API 요청 실패: 상태 코드 {response.status_code}")
                if page == 1:
                    print(f"응답 내용: {response.text[:500]}")
                break
            
            root = ET.fromstring(response.content)
            
            # resultCode 확인
            result_code = root.find('header/resultCode')
            if result_code is not None and result_code.text != '00':
                result_msg = root.find('header/resultMsg')
                error_msg = result_msg.text if result_msg is not None else '알 수 없는 오류'
                print(f"API 오류: {error_msg}")
                if page == 1:
                    return []
                break
            
            body = root.find('body')
            
            if body is None:
                print("응답에 body 요소가 없습니다.")
                if page == 1:
                    return []
                break
            
            # totalCount 확인 (첫 페이지에서만)
            if page == 1:
                total_count_elem = body.find('totalCount')
                total_count_text = total_count_elem.text if total_count_elem is not None else '0'
                total_count = int(total_count_text)
                
                if total_count == 0:
                    print(f"검색 결과가 없습니다. (totalCount: {total_count_text})")
                    return []
                
                print(f"전체 검색 결과: {total_count}건, 페이지네이션 시작...")
            
            items = body.find('items')
            if items is None:
                print(f"페이지 {page}: items 요소가 없습니다.")
                break
            
            page_results = []
            for item in items.findall('item'):
                result = {}
                for child in item:
                    result[child.tag] = child.text if child.text else None
                page_results.append(result)
            
            if not page_results:
                # 더 이상 결과가 없으면 종료
                break
            
            all_results.extend(page_results)
            
            # 진행 상황 출력
            if page % 10 == 0 or len(all_results) >= total_count:
                print(f"진행 중... {len(all_results)}/{total_count}건 수집 완료 (페이지 {page})")
            
            # 모든 결과를 가져왔으면 종료
            if len(all_results) >= total_count:
                break
            
            page += 1
            
            # 무한 루프 방지 (최대 1000페이지)
            if page > 1000:
                print(f"⚠️ 최대 페이지 수(1000)에 도달했습니다. 현재까지 {len(all_results)}건 수집했습니다.")
                break
            
        except ET.ParseError as e:
            print(f"페이지 {page} XML 파싱 오류: {e}")
            if page == 1:
                return []
            break
        except Exception as e:
            print(f"페이지 {page} 조회 오류: {e}")
            if page == 1:
                import traceback
                traceback.print_exc()
                return []
            break
    
    print(f"✅ 총 {len(all_results)}건 수집 완료")
    return all_results

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
