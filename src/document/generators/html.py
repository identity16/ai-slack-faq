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
        """
        용어집 생성
        
        Args:
            semantic_data: 의미 데이터 목록
            
        Returns:
            HTML 형식의 용어집
        """
        # 용어집 데이터 필터링
        glossary_items = [item for item in semantic_data if item["type"] == "glossary"]
        
        # 용어집 항목이 없으면 참조 데이터 사용
        if not glossary_items:
            glossary_items = [item for item in semantic_data if item["type"] == "reference"]
        
        if not glossary_items:
            return self.env.get_template("glossary_empty.html").render()
        
        # 정규화된 항목 생성
        normalized_items = []
        for item in glossary_items:
            term = item.get("term") or item.get("content", "")
            if not term:
                continue
                
            normalized_item = {
                "term": term,
                "definition": item.get("definition", ""),
                "term_type": item.get("term_type", "etc"),
                "confidence": item.get("confidence", ""),
                "needs_review": item.get("needs_review", False),
                "alternative_definitions": item.get("alternative_definitions", []),
                "keywords": item.get("keywords", []),
                "domain_hints": item.get("domain_hints", [])
            }
            normalized_items.append(normalized_item)
        
        # 용어 정렬
        sorted_items = sorted(normalized_items, key=lambda x: x["term"].lower())
        
        # 첫 글자 기준으로 그룹화
        groups = {}
        korean_consonants = ['ㄱ', 'ㄴ', 'ㄷ', 'ㄹ', 'ㅁ', 'ㅂ', 'ㅅ', 'ㅇ', 'ㅈ', 'ㅊ', 'ㅋ', 'ㅌ', 'ㅍ', 'ㅎ']
        
        for item in sorted_items:
            term = item["term"]
            first_char = term[0]
            
            # 한글인 경우 초성 추출
            if '가' <= first_char <= '힣':
                char_code = ord(first_char) - ord('가')
                consonant_index = char_code // 588
                consonant = korean_consonants[consonant_index]
                group_key = consonant
            elif first_char.isalpha():
                group_key = first_char.upper()
            elif first_char.isdigit():
                group_key = '0-9'
            else:
                group_key = '#'
            
            if group_key not in groups:
                groups[group_key] = []
            groups[group_key].append(item)
        
        # 그룹 정렬
        sorted_groups = {}
        
        # 한글 초성 먼저
        for consonant in korean_consonants:
            if consonant in groups:
                sorted_groups[consonant] = groups[consonant]
        
        # 영문 알파벳
        for char in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ':
            if char in groups:
                sorted_groups[char] = groups[char]
        
        # 숫자와 특수문자
        if '0-9' in groups:
            sorted_groups['0-9'] = groups['0-9']
        if '#' in groups:
            sorted_groups['#'] = groups['#']
        
        # 템플릿 렌더링
        # 서비스, 개발, 디자인, 마케팅, 기타 등등 분리
        service_terms = [item for item in sorted_items if item["term_type"] == "service"]
        development_terms = [item for item in sorted_items if item["term_type"] == "development"]
        design_terms = [item for item in sorted_items if item["term_type"] == "design"]
        marketing_terms = [item for item in sorted_items if item["term_type"] == "marketing"]
        etc_terms = [item for item in sorted_items if item["term_type"] == "etc"]
        
        return self.env.get_template("glossary.html").render(
            groups=sorted_groups,
            service_terms=service_terms,
            development_terms=development_terms,
            design_terms=design_terms,
            marketing_terms=marketing_terms,
            etc_terms=etc_terms,
            generation_time=datetime.now().strftime("%Y-%m-%d %H:%M")
        ) 