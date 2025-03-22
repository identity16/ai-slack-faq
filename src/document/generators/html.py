"""
HTML Document Generator

시맨틱 데이터를 HTML 형식의 문서로 변환하는 모듈입니다.
"""

import os
from typing import Dict, Any, List
from datetime import datetime
from jinja2 import Environment, FileSystemLoader, select_autoescape

from .. import DocumentGenerator, DocumentType

class HTMLGenerator(DocumentGenerator):
    """HTML 문서 생성기"""
    
    def __init__(self, config: Dict[str, Any] = None):
        """
        초기화
        
        Args:
            config: 설정 정보 (옵션)
        """
        template_dir = config.get("template_dir") if config else "resources/templates"
        self.env = Environment(
            loader=FileSystemLoader(template_dir),
            autoescape=select_autoescape(['html', 'xml'])
        )
    
    async def generate(self, semantic_data: List[Dict[str, Any]], doc_type: str) -> str:
        """
        시맨틱 데이터를 HTML 문서로 변환
        
        Args:
            semantic_data: 시맨틱 데이터 목록
            doc_type: 문서 유형
            
        Returns:
            생성된 HTML 문서
        """
        if doc_type == DocumentType.FAQ:
            return await self._generate_faq(semantic_data)
        elif doc_type == DocumentType.GUIDE:
            return await self._generate_guide(semantic_data)
        elif doc_type == DocumentType.RELEASE_NOTE:
            return await self._generate_release_note(semantic_data)
        elif doc_type == DocumentType.GLOSSARY:
            return await self._generate_glossary(semantic_data)
        else:
            raise ValueError(f"지원하지 않는 문서 유형입니다: {doc_type}")
    
    async def save(self, content: str, output_path: str) -> None:
        """
        HTML 문서 저장
        
        Args:
            content: 문서 내용
            output_path: 저장 경로
        """
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(content)
    
    async def _generate_faq(self, semantic_data: List[Dict[str, Any]]) -> str:
        """FAQ 문서 생성"""
        qa_data = [d for d in semantic_data if d["type"] == "qa"]
        
        # 주요 카테고리 정의 및 매핑 - 키워드를 기반으로 주요 카테고리로 정리
        main_categories = {
            "설치 및 설정": ["설치", "설정", "환경", "시작하기"],
            "기본 기능": ["기본", "사용법", "기능"],
            "고급 기능": ["고급", "응용", "확장"],
            "문제 해결": ["오류", "에러", "버그", "문제", "해결"],
            "보안 및 권한": ["보안", "권한", "인증", "암호"],
            "성능 최적화": ["성능", "최적화", "속도"],
            "통합 및 연동": ["통합", "연동", "API", "외부"],
            "기타": []  # 분류되지 않은 항목들을 위한 카테고리
        }
        
        # 각 질문을 적절한 카테고리에 분류
        categorized_qa = {category: [] for category in main_categories.keys()}
        
        for qa in qa_data:
            # 키워드 기반으로 가장 적합한 카테고리 찾기
            matched_category = None
            for category, keywords in main_categories.items():
                if any(kw in qa["keywords"] for kw in keywords):
                    matched_category = category
                    break
            
            # 매칭되는 카테고리가 없으면 '기타'로 분류
            if not matched_category:
                matched_category = "기타"
            
            # 해당 카테고리에 질문 추가 (중복 방지)
            if qa not in categorized_qa[matched_category]:
                categorized_qa[matched_category].append(qa)
        
        # 빈 카테고리 제거
        categorized_qa = {k: v for k, v in categorized_qa.items() if v}
        
        # 각 카테고리 내에서 서브 카테고리로 더 세분화 (선택적)
        structured_data = {}
        for category, questions in categorized_qa.items():
            sub_categories = {}
            for qa in questions:
                primary_keyword = qa["keywords"][0] if qa["keywords"] else "일반"
                if primary_keyword not in sub_categories:
                    sub_categories[primary_keyword] = []
                sub_categories[primary_keyword].append(qa)
            structured_data[category] = sub_categories
        
        template = self.env.get_template("faq.html")
        return template.render(
            title="자주 묻는 질문 (FAQ)",
            updated_at=datetime.now().strftime("%Y-%m-%d %H:%M"),
            structured_data=structured_data
        )
    
    async def _generate_guide(self, semantic_data: List[Dict[str, Any]]) -> str:
        """가이드 문서 생성"""
        instructions = [d for d in semantic_data if d["type"] == "instruction"]
        insights = [d for d in semantic_data if d["type"] == "insight"]
        
        template = self.env.get_template("guide.html")
        return template.render(
            title="사용자 가이드",
            updated_at=datetime.now().strftime("%Y-%m-%d %H:%M"),
            instructions=instructions,
            insights=insights
        )
    
    async def _generate_release_note(self, semantic_data: List[Dict[str, Any]]) -> str:
        """릴리스 노트 생성"""
        changes = []
        features = []
        fixes = []
        
        for data in semantic_data:
            if "release" in data.get("keywords", []):
                if "feature" in data.get("keywords", []):
                    features.append(data)
                elif "fix" in data.get("keywords", []):
                    fixes.append(data)
                else:
                    changes.append(data)
        
        template = self.env.get_template("release_note.html")
        return template.render(
            title="릴리스 노트",
            updated_at=datetime.now().strftime("%Y-%m-%d %H:%M"),
            features=features,
            fixes=fixes,
            changes=changes
        )
    
    async def _generate_glossary(self, semantic_data: List[Dict[str, Any]]) -> str:
        """용어집 생성"""
        # 수정: GLOSSARY 타입의 데이터를 사용하여 용어집 생성
        glossary_items = [d for d in semantic_data if d["type"] == "glossary"]
        
        if not glossary_items:
            # GLOSSARY 타입 데이터가 없으면 참조 데이터로 대체
            glossary_items = [d for d in semantic_data if d["type"] == "reference"]
        
        # 표준화된 아이템 구조로 변환
        normalized_items = []
        for item in glossary_items:
            normalized_item = {
                "term": item.get("term", item.get("content", "")),
                "definition": item.get("definition", item.get("description", "")),
                "confidence": item.get("confidence", "high"),
                "needs_review": item.get("needs_review", False),
                "keywords": item.get("keywords", []),
                "domain_hint": item.get("domain_hint", ""),
                "alternative_definitions": item.get("alternative_definitions", []),
                "source": item.get("source", {})
            }
            
            if normalized_item["term"]:  # 용어가 비어있지 않은 경우만 추가
                normalized_items.append(normalized_item)
        
        # 용어 이름 기준으로 정렬
        normalized_items.sort(key=lambda x: x["term"].lower())
        
        # 알파벳/초성별로 그룹화
        groups = {}
        for item in normalized_items:
            # 첫 글자 추출
            first_char = item["term"][0].upper() if item["term"] else ""
            
            # 한글인 경우 자음으로 분류
            if '가' <= first_char <= '힣':
                first_char = self._get_korean_consonant(first_char)
            
            # 숫자인 경우 '#'으로 분류
            elif '0' <= first_char <= '9':
                first_char = '#'
            
            # 특수문자인 경우 '_'로 분류
            elif not first_char.isalnum():
                first_char = '_'
            
            if first_char not in groups:
                groups[first_char] = []
            
            groups[first_char].append(item)
        
        # 그룹 키를 정렬 (숫자, 알파벳, 한글 초성 순)
        sorted_keys = sorted(groups.keys(), key=self._sort_key)
        sorted_groups = {k: groups[k] for k in sorted_keys}
        
        template = self.env.get_template("glossary.html")
        return template.render(
            title="용어집",
            updated_at=datetime.now().strftime("%Y-%m-%d %H:%M"),
            groups=sorted_groups
        )
    
    def _get_korean_consonant(self, char: str) -> str:
        """한글 문자에서 초성 추출"""
        if not '가' <= char <= '힣':
            return char
            
        # 한글 유니코드 계산
        code = ord(char) - ord('가')
        
        # 초성 추출 (19개의 초성)
        consonants = [
            'ㄱ', 'ㄲ', 'ㄴ', 'ㄷ', 'ㄸ', 'ㄹ', 'ㅁ', 'ㅂ', 'ㅃ', 
            'ㅅ', 'ㅆ', 'ㅇ', 'ㅈ', 'ㅉ', 'ㅊ', 'ㅋ', 'ㅌ', 'ㅍ', 'ㅎ'
        ]
        
        # 초성 인덱스 계산 (각 초성마다 21*28개의 조합이 있음)
        consonant_index = code // (21 * 28)
        return consonants[consonant_index]
    
    def _sort_key(self, key: str) -> tuple:
        """정렬 키 생성 (숫자, 영문, 한글 초성 순)"""
        # 숫자는 가장 앞에
        if key == '#':
            return (0, key)
        # 영문은 다음
        elif 'A' <= key <= 'Z':
            return (1, key)
        # 특수문자
        elif key == '_':
            return (2, key)
        # 한글 초성은 그 다음
        elif key in ['ㄱ', 'ㄲ', 'ㄴ', 'ㄷ', 'ㄸ', 'ㄹ', 'ㅁ', 'ㅂ', 'ㅃ', 
                      'ㅅ', 'ㅆ', 'ㅇ', 'ㅈ', 'ㅉ', 'ㅊ', 'ㅋ', 'ㅌ', 'ㅍ', 'ㅎ']:
            # 초성 순서에 따라 정렬
            consonants = [
                'ㄱ', 'ㄲ', 'ㄴ', 'ㄷ', 'ㄸ', 'ㄹ', 'ㅁ', 'ㅂ', 'ㅃ', 
                'ㅅ', 'ㅆ', 'ㅇ', 'ㅈ', 'ㅉ', 'ㅊ', 'ㅋ', 'ㅌ', 'ㅍ', 'ㅎ'
            ]
            return (3, consonants.index(key))
        # 그 외
        else:
            return (4, key) 