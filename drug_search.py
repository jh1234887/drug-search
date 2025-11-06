import requests
import xml.etree.ElementTree as ET
import pandas as pd
import os
import argparse
from typing import Optional, List, Dict
import urllib3

# SSL 경고 비활성화 (필요한 경우)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# API 키 설정
KEY = "YOUR_API_KEY_HERE"  # 여기에 실제 API 키를 입력하세요


def load_drug_data_api(output_path: str = 'drug_data_api.xlsx', per_page: int = 1000) -> Optional[pd.DataFrame]:
    """
    공공데이터 API에서 모든 의약품 데이터를 페이지네이션으로 조회하여 엑셀로 저장
    
    Args:
        output_path: 저장할 엑셀 파일 경로
        per_page: 페이지당 조회 건수 (최대 1000 권장)
        
    Returns:
        DataFrame 또는 None
    """
    baseurl = "https://api.odcloud.kr/api"
    endpoint = "/15118958/v1/uddi:6753c7f1-65ed-4bbe-9e98-cd6b7b156a92"
    
    all_data = []
    page = 1
    total_count = 0
    
    try:
        print(f"\n{'='*80}\nAPI Endpoint: {endpoint}\n{'='*80}")
        print(f"페이지당 조회 건수: {per_page}건")
        
        while True:
            params = {
                "serviceKey": JHKEY,
                "page": page,
                "perPage": per_page,
                "returnType": "JSON"
            }
            
            print(f"\n[페이지 {page}] 데이터 조회 중...", end=" ")
            
            response = requests.get(
                baseurl + endpoint, 
                params=params, 
                timeout=30, 
                verify=False
            )
            
            if response.status_code != 200:
                print(f"\n❌ API 요청 실패 (상태 코드: {response.status_code})")
                print(f"응답 내용: {response.text[:500]}")
                break
            
            data = response.json()
            
            # 첫 페이지에서 전체 건수 확인
            if page == 1:
                total_count = data.get("totalCount", 0)
                print(f"\n전체 데이터 건수: {total_count}건")
                print(f"예상 페이지 수: {(total_count + per_page - 1) // per_page}페이지")
            
            items = data.get("data", [])
            
            if not items:
                print("완료!")
                break
            
            all_data.extend(items)
            print(f"✓ ({len(all_data)}/{total_count}건 수집)")
            
            # 모든 데이터를 수집했으면 종료
            if len(all_data) >= total_count:
                break
            
            page += 1
        
        if all_data:
            df = pd.DataFrame(all_data)
            print(f"\n{'='*80}")
            print(f"✅ 총 {len(all_data)}건 수집 완료")
            print(f"데이터프레임 크기: {df.shape}")
            print("\n첫 3개 행:")
            print(df.head(3))
            
            # 엑셀 저장
            df.to_excel(output_path, index=False)
            print(f"\n✅ 데이터 저장 완료: {output_path}")
            return df
        else:
            print("⚠️ 수집된 데이터가 없습니다.")
            return None
            
    except Exception as e:
        print(f"\n❌ 오류 발생: {str(e)}")
        if all_data:
            print(f"⚠️ 부분 데이터 {len(all_data)}건은 수집되었습니다.")
            df = pd.DataFrame(all_data)
            df.to_excel(output_path.replace('.xlsx', '_partial.xlsx'), index=False)
        return None


def search_drug_info(
    gnlNmCd: Optional[str] = None,
    itmNm: Optional[str] = None,
    mdsCd: Optional[str] = None,
    mnfEntpNm: Optional[str] = None,
    num_rows: int = 10
) -> Optional[str]:
    """
    의약품 정보를 검색하고 첫 번째 결과의 성분코드를 반환
    
    Args:
        gnlNmCd: 성분코드 (일반명코드)
        itmNm: 품목명
        mdsCd: 제품코드
        mnfEntpNm: 제조업체명
        num_rows: 검색할 최대 결과 수
        
    Returns:
        첫 번째 검색 결과의 일반명코드 또는 None
    """
    service_key = KEY
    endpoint = "https://apis.data.go.kr/B551182/dgamtCrtrInfoService1.2/getDgamtList"
    
    # 검색 조건 설정
    search_params = {}
    search_desc = []
    
    if gnlNmCd:
        search_params["gnlNmCd"] = gnlNmCd
        search_desc.append(f"성분코드: {gnlNmCd}")
    if itmNm:
        search_params["itmNm"] = itmNm
        search_desc.append(f"품목명: {itmNm}")
    if mdsCd:
        search_params["mdsCd"] = mdsCd
        search_desc.append(f"제품코드: {mdsCd}")
    if mnfEntpNm:
        search_params["mnfEntpNm"] = mnfEntpNm
        search_desc.append(f"제조업체: {mnfEntpNm}")
    
    if not search_params:
        print("❌ 검색 조건이 없습니다.")
        return None
    
    params = {
        "ServiceKey": service_key,
        "numOfRows": str(num_rows),
        "pageNo": "1"
    }
    params.update(search_params)
    
    print(f"\n{'='*80}")
    print(f"의약품 검색")
    print(f"검색 조건: {', '.join(search_desc)}")
    print('='*80)
    
    try:
        response = requests.get(endpoint, params=params, verify=False, timeout=30)
        
        if response.status_code != 200:
            print(f"❌ API 요청 실패 (상태 코드: {response.status_code})")
            return None
        
        # XML 파싱
        root = ET.fromstring(response.content)
        body = root.find('body')
        
        if body is None:
            print("❌ 응답에 body 요소가 없습니다.")
            return None
        
        total_count = body.find('totalCount')
        total_count_text = total_count.text if total_count is not None else '0'
        
        print(f"검색 건수: {total_count_text}건")
        
        first_gnlNmCd = None
        
        if int(total_count_text) > 0:
            items = body.find('items')
            if items is not None:
                for i, item in enumerate(items.findall('item')[:5], 1):
                    itmNm_elem = item.find('itmNm')
                    gnlNmCd_elem = item.find('gnlNmCd')
                    mdsCd_elem = item.find('mdsCd')
                    mnfEntpNm_elem = item.find('mnfEntpNm')
                    
                    itmNm_text = itmNm_elem.text if itmNm_elem is not None else 'N/A'
                    gnlNmCd_text = gnlNmCd_elem.text if gnlNmCd_elem is not None else 'N/A'
                    mdsCd_text = mdsCd_elem.text if mdsCd_elem is not None else 'N/A'
                    mnfEntpNm_text = mnfEntpNm_elem.text if mnfEntpNm_elem is not None else 'N/A'
                    
                    print(f"\n  [{i}] {itmNm_text}")
                    print(f"      성분코드: {gnlNmCd_text}")
                    print(f"      제품코드: {mdsCd_text}")
                    print(f"      제조업체: {mnfEntpNm_text}")
                    
                    # 첫 번째 결과의 일반명코드 저장
                    if i == 1 and first_gnlNmCd is None and gnlNmCd_text != 'N/A':
                        first_gnlNmCd = gnlNmCd_text
                
                print("\n✅ 검색 성공!")
                return first_gnlNmCd
            else:
                print("⚠️ items 요소가 없습니다.")
        else:
            print("❌ 검색 결과 없음")
            
    except ET.ParseError as e:
        print(f"❌ XML 파싱 오류: {str(e)}")
    except Exception as e:
        print(f"❌ 오류 발생: {str(e)}")
    
    return None


def find_identical_ingredients(gnlNmCd: str, df: pd.DataFrame) -> pd.DataFrame:
    """
    동일 성분의 의약품 찾기
    
    Args:
        gnlNmCd: 일반명코드
        df: 의약품 데이터프레임
        
    Returns:
        동일 성분 의약품 데이터프레임
    """
    if df is None or df.empty:
        print("⚠️ 데이터프레임이 비어있습니다.")
        return pd.DataFrame()
    
    # 주성분코드 컬럼명 확인
    component_col = None
    for col in df.columns:
        if '주성분' in col and '코드' in col:
            component_col = col
            break
    
    if component_col is None:
        print("⚠️ 주성분코드 컬럼을 찾을 수 없습니다.")
        print(f"사용 가능한 컬럼: {df.columns.tolist()}")
        return pd.DataFrame()
    
    print(f"\n{'='*80}")
    print(f"동일성분 검색: {gnlNmCd}")
    print('='*80)
    
    identical = df[df[component_col] == gnlNmCd]
    
    print(f"\n동일성분 의약품 리스트 (총 {len(identical)}개):")
    
    if len(identical) > 0:
        for idx, row in identical.head(10).iterrows():
            print(f"\n  [{idx}]")
            for col, val in row.items():
                if pd.notna(val):
                    print(f"    {col}: {val}")
    else:
        print("  검색 결과 없음")
    
    return identical


def search_by_component_code(gnlNmCd: str, df: Optional[pd.DataFrame] = None) -> pd.DataFrame:
    """
    성분코드로 직접 동일성분 의약품 검색
    
    Args:
        gnlNmCd: 일반명코드 (성분코드)
        df: 의약품 데이터프레임 (None이면 자동으로 로드)
        
    Returns:
        동일성분 의약품 데이터프레임
    """
    print(f"\n{'='*80}")
    print(f"성분코드로 검색: {gnlNmCd}")
    print('='*80)
    
    # 데이터프레임이 없으면 로드
    if df is None:
        print("\n의약품 데이터 로드 중...")
        df = load_drug_data_api()
        
        if df is None:
            print("❌ 데이터 로드 실패")
            return pd.DataFrame()
    
    # 동일성분 의약품 검색
    identical_drugs = find_identical_ingredients(gnlNmCd, df)
    
    return identical_drugs


def main_with_args():
    """
    argparse를 사용한 메인 실행 함수
    """
    parser = argparse.ArgumentParser(
        description='의약품 정보 조회 프로그램',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
사용 예시:
  # 품목명으로 검색
  python script.py --itmNm 졸피드정
  
  # 성분코드로 검색
  python script.py --gnlNmCd 281700ATB
  
  # 제품코드로 검색
  python script.py --mdsCd A03850091
  
  # 제조업체로 검색
  python script.py --mnfEntpNm 건일제약
  
  # 여러 조건 조합
  python script.py --itmNm 아시콘정 --mnfEntpNm 건일제약
  
  # 동일성분 검색 생략
  python script.py --itmNm 졸피드정 --no-search-identical
        """
    )
    
    # 검색 옵션
    parser.add_argument('--gnlNmCd', type=str, help='성분코드 (일반명코드)')
    parser.add_argument('--itmNm', type=str, help='품목명')
    parser.add_argument('--mdsCd', type=str, help='제품코드')
    parser.add_argument('--mnfEntpNm', type=str, help='제조업체명')
    
    # 추가 옵션
    parser.add_argument('--no-search-identical', action='store_true', 
                       help='동일성분 의약품 검색 생략')
    parser.add_argument('--output', type=str, default='drug_data_api.xlsx',
                       help='저장할 엑셀 파일 경로 (기본값: drug_data_api.xlsx)')
    
    args = parser.parse_args()
    
    # 검색 조건이 하나도 없으면 에러
    if not any([args.gnlNmCd, args.itmNm, args.mdsCd, args.mnfEntpNm]):
        parser.print_help()
        print("\n❌ 오류: 최소 하나의 검색 조건을 입력해야 합니다.")
        return
    
    print("=" * 80)
    print("의약품 정보 조회 프로그램")
    print("=" * 80)
    
    # 의약품 정보 검색
    if not args.gnlNmCd:
        found_gnlNmCd = search_drug_info(
            gnlNmCd=args.gnlNmCd,
            itmNm=args.itmNm,
            mdsCd=args.mdsCd,
            mnfEntpNm=args.mnfEntpNm
        )
    
    # 동일성분 검색
    if not args.no_search_identical:
        # 성분코드 결정 (직접 입력 또는 검색 결과)
        target_gnlNmCd = args.gnlNmCd if args.gnlNmCd else found_gnlNmCd
        
        if target_gnlNmCd:
            print(f"\n{'='*80}")
            print("의약품 데이터 로드 중...")
            print('='*80)
            
            df = load_drug_data_api(output_path=args.output, per_page=args.per_page)
            
            if df is not None:
                find_identical_ingredients(target_gnlNmCd, df)
        else:
            print("\n⚠️ 성분코드를 찾을 수 없어 동일성분 검색을 건너뜁니다.")
    
    print(f"\n{'='*80}")
    print("프로그램 종료")
    print('='*80)


if __name__ == "__main__":
    # argparse 사용
    main_with_args()
    
    # 또는 직접 함수 호출 (코드 내에서 실행할 때)
    # search_drug_info(itmNm="졸피드정")
    # search_drug_info(gnlNmCd="281700ATB")
    # search_drug_info(mdsCd="A03850091")
    # search_drug_info(mnfEntpNm="건일제약")