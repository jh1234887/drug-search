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
        
        # 성분코드만 입력된 경우 동일성분 의약품 검색
        if gnlNmCd and not any([itmNm, mdsCd, mnfEntpNm]):
            # 동일성분 의약품 검색 로직
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
                    'isIdenticalSearch': True,
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
                
                search_results = get_detailed_search_results(
                    itmNm=str(item_name),
                    num_rows=100  # 각 품목명당 최대 100개
                )
                
                # 중복 제거 (제품코드 기준)
                for result in search_results:
                    mds_cd = result.get('mdsCd')
                    if mds_cd and mds_cd not in seen_items:
                        seen_items.add(mds_cd)
                        all_results.append(result)
            
            return jsonify({
                'success': True,
                'isIdenticalSearch': False,  # 일반 검색 결과로 표시
                'results': all_results
            })
        
        # 그 외의 경우 일반 검색
        search_results = get_detailed_search_results(
            gnlNmCd=gnlNmCd,
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
    """상세 검색 결과 반환"""
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
    
    params = {
        "ServiceKey": KEY,
        "numOfRows": str(num_rows),
        "pageNo": "1"
    }
    params.update(search_params)
    
    try:
        response = requests.get(endpoint, params=params, verify=False, timeout=30)
        
        if response.status_code != 200:
            print(f"API 요청 실패: 상태 코드 {response.status_code}")
            print(f"응답 내용: {response.text[:500]}")
            return []
        
        root = ET.fromstring(response.content)
        
        # resultCode 확인
        result_code = root.find('header/resultCode')
        if result_code is not None and result_code.text != '00':
            result_msg = root.find('header/resultMsg')
            error_msg = result_msg.text if result_msg is not None else '알 수 없는 오류'
            print(f"API 오류: {error_msg}")
            return []
        
        body = root.find('body')
        
        if body is None:
            print("응답에 body 요소가 없습니다.")
            return []
        
        # totalCount 확인
        total_count = body.find('totalCount')
        total_count_text = total_count.text if total_count is not None else '0'
        
        if int(total_count_text) == 0:
            print(f"검색 결과가 없습니다. (totalCount: {total_count_text})")
            return []
        
        items = body.find('items')
        if items is None:
            print("응답에 items 요소가 없습니다.")
            return []
        
        results = []
        for item in items.findall('item'):
            result = {}
            for child in item:
                result[child.tag] = child.text if child.text else None
            results.append(result)
        
        return results
    except ET.ParseError as e:
        print(f"XML 파싱 오류: {e}")
        if 'response' in locals():
            print(f"응답 내용: {response.content[:500]}")
        return []
    except Exception as e:
        print(f"오류 발생: {e}")
        import traceback
        traceback.print_exc()
        return []

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
