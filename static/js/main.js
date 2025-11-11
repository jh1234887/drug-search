// DOM 요소
const searchForm = document.getElementById('searchForm');
const searchBtn = document.getElementById('searchBtn');
const resetBtn = document.getElementById('resetBtn');
const loading = document.getElementById('loading');
const resultsSection = document.getElementById('resultsSection');
const identicalSection = document.getElementById('identicalSection');
const searchResults = document.getElementById('searchResults');
const identicalResults = document.getElementById('identicalResults');
const errorMessage = document.getElementById('errorMessage');
const resultCount = document.getElementById('resultCount');
const identicalCount = document.getElementById('identicalCount');

// 검색 폼 제출
searchForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const formData = {
        itmNm: document.getElementById('itmNm').value.trim(),
        gnlNmCd: document.getElementById('gnlNmCd').value.trim(),
        mdsCd: document.getElementById('mdsCd').value.trim(),
        mnfEntpNm: document.getElementById('mnfEntpNm').value.trim(),
        num_rows: 20
    };
    
    // 최소 하나의 검색 조건 확인
    if (!Object.values(formData).slice(0, 4).some(val => val)) {
        showError('최소 하나의 검색 조건을 입력해주세요.');
        return;
    }
    
    await performSearch(formData);
});

// 초기화 버튼
resetBtn.addEventListener('click', () => {
    searchForm.reset();
    hideAllSections();
});

// 검색 실행
async function performSearch(formData) {
    try {
        showLoading();
        hideError();
        hideAllSections();
        
        // 검색 API 호출
        const searchResponse = await fetch('/api/search', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(formData)
        });
        
        const searchData = await searchResponse.json();
        
        if (!searchData.success) {
            throw new Error(searchData.error || '검색에 실패했습니다.');
        }
        
        // 성분코드로만 검색한 경우 (동일성분 검색)
        if (searchData.isIdenticalSearch) {
            if (searchData.results && searchData.results.length > 0) {
                displayIdenticalDrugs(searchData.results);
            } else {
                showError('동일성분 의약품이 없습니다.');
            }
        } else {
            // 일반 검색 결과 표시
            if (searchData.results && searchData.results.length > 0) {
                displaySearchResults(searchData.results);
            } else {
                showError('검색 결과가 없습니다.');
            }
        }
        
    } catch (error) {
        showError(`오류가 발생했습니다: ${error.message}`);
    } finally {
        hideLoading();
    }
}

// 검색 결과 표시
function displaySearchResults(results) {
    searchResults.innerHTML = '';
    resultCount.textContent = `${results.length}건`;
    
    results.forEach((item, index) => {
        const card = createDrugCard(item, index);
        searchResults.appendChild(card);
    });
    
    resultsSection.classList.remove('hidden');
}

// 동일성분 의약품 로드
async function loadIdenticalDrugs(gnlNmCd) {
    try {
        const response = await fetch('/api/identical', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ gnlNmCd })
        });
        
        const data = await response.json();
        
        if (data.success && data.results && data.results.length > 0) {
            displayIdenticalDrugs(data.results);
        }
    } catch (error) {
        console.error('동일성분 의약품 로드 실패:', error);
    }
}

// 동일성분 의약품 표시
function displayIdenticalDrugs(results) {
    identicalResults.innerHTML = '';
    identicalCount.textContent = `${results.length}건`;
    
    results.forEach((item, index) => {
        const card = createDrugCard(item, index);
        identicalResults.appendChild(card);
    });
    
    identicalSection.classList.remove('hidden');
}

// 의약품 카드 생성
function createDrugCard(item, index) {
    const card = document.createElement('div');
    card.className = 'drug-card';
    
    const title = item.itmNm || item.품목명 || '정보 없음';
    const gnlNmCd = item.gnlNmCd || item.주성분코드 || item['주성분코드'] || 'N/A';
    const mdsCd = item.mdsCd || item.제품코드 || item['제품코드'] || 'N/A';
    const mnfEntpNm = item.mnfEntpNm || item.제조업체명 || item['제조업체명'] || 'N/A';
    
    card.innerHTML = `
        <div class="drug-card-title">${title}</div>
        <div class="drug-card-info">
            <div class="drug-card-item">
                <span class="drug-card-label">성분코드</span>
                <span class="drug-card-value">${gnlNmCd}</span>
            </div>
            <div class="drug-card-item">
                <span class="drug-card-label">제품코드</span>
                <span class="drug-card-value">${mdsCd}</span>
            </div>
            <div class="drug-card-item">
                <span class="drug-card-label">제조업체</span>
                <span class="drug-card-value">${mnfEntpNm}</span>
            </div>
        </div>
    `;
    
    return card;
}

// UI 헬퍼 함수
function showLoading() {
    loading.classList.remove('hidden');
    searchBtn.disabled = true;
}

function hideLoading() {
    loading.classList.add('hidden');
    searchBtn.disabled = false;
}

function showError(message) {
    errorMessage.textContent = message;
    errorMessage.classList.remove('hidden');
}

function hideError() {
    errorMessage.classList.add('hidden');
}

function hideAllSections() {
    resultsSection.classList.add('hidden');
    identicalSection.classList.add('hidden');
}

