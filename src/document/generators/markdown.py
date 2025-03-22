"""
Markdown Document Generator

시맨틱 데이터를 Markdown 형식의 문서로 변환하는 모듈입니다.
"""

import os
from typing import Dict, Any, List
from datetime import datetime
import re

from .. import DocumentGenerator, DocumentType

class MarkdownGenerator(DocumentGenerator):
    """Markdown 문서 생성기"""
    
    def __init__(self, config: Dict[str, Any] = None):
        """
        초기화
        
        Args:
            config: 설정 정보 (옵션)
        """
        self.config = config or {}
    
    async def generate(self, semantic_data: List[Dict[str, Any]], doc_type: str) -> str:
        """
        시맨틱 데이터를 Markdown 문서로 변환
        
        Args:
            semantic_data: 시맨틱 데이터 목록
            doc_type: 문서 유형
            
        Returns:
            생성된 Markdown 문서
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
        Markdown 문서 저장
        
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
        
        # Markdown 생성
        lines = [
            "# 자주 묻는 질문 (FAQ)",
            f"\n_마지막 업데이트: {datetime.now().strftime('%Y-%m-%d %H:%M')}_\n",
            "\n## 목차\n"
        ]
        
        # 목차 생성
        for category in categorized_qa.keys():
            category_id = category.lower().replace(' ', '-').replace('및', '').replace('_', '')
            lines.append(f"- [{category}](#{category_id})")
        
        # 내용 생성
        for category, questions in categorized_qa.items():
            category_id = category.lower().replace(' ', '-').replace('및', '').replace('_', '')
            lines.append(f"\n## {category}\n")
            
            # 서브 카테고리로 더 세분화 (선택적)
            sub_categories = {}
            for qa in questions:
                primary_keyword = qa["keywords"][0] if qa["keywords"] else "일반"
                if primary_keyword not in sub_categories:
                    sub_categories[primary_keyword] = []
                sub_categories[primary_keyword].append(qa)
            
            # 서브 카테고리별로 질문 표시
            for sub_cat, sub_questions in sub_categories.items():
                if len(sub_categories) > 1:  # 서브 카테고리가 여러 개일 때만 표시
                    lines.append(f"### {sub_cat}\n")
                
                # 질문과 답변 표시
                for idx, qa in enumerate(sub_questions, 1):
                    lines.append(f"**Q{idx}: {qa['question']}**\n\n{qa['answer']}\n")
            
            # 서브 카테고리가 없을 경우 직접 질문 표시
            if not sub_categories:
                for idx, qa in enumerate(questions, 1):
                    lines.append(f"**Q{idx}: {qa['question']}**\n\n{qa['answer']}\n")
        
        return "\n".join(lines)
    
    async def _generate_guide(self, semantic_data: List[Dict[str, Any]]) -> str:
        """가이드 문서 생성"""
        instructions = [d for d in semantic_data if d["type"] == "instruction"]
        insights = [d for d in semantic_data if d["type"] == "insight"]
        
        lines = [
            "# 사용자 가이드",
            f"\n_마지막 업데이트: {datetime.now().strftime('%Y-%m-%d %H:%M')}_\n",
            "\n## 주요 지침\n"
        ]
        
        # 작업 지침 추가
        for instruction in instructions:
            lines.extend([
                f"### {instruction['content']}\n",
                *[f"- {line}" for line in instruction.get("details", [])]
            ])
        
        # 인사이트 추가
        if insights:
            lines.extend([
                "\n## 유용한 팁과 인사이트\n",
                *[f"- {insight['content']}" for insight in insights]
            ])
        
        return "\n".join(lines)
    
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
        
        lines = [
            "# 릴리스 노트",
            f"\n_마지막 업데이트: {datetime.now().strftime('%Y-%m-%d %H:%M')}_\n"
        ]
        
        if features:
            lines.extend([
                "\n## 새로운 기능\n",
                *[f"- {feature['content']}" for feature in features]
            ])
        
        if fixes:
            lines.extend([
                "\n## 버그 수정\n",
                *[f"- {fix['content']}" for fix in fixes]
            ])
        
        if changes:
            lines.extend([
                "\n## 기타 변경사항\n",
                *[f"- {change['content']}" for change in changes]
            ])
        
        return "\n".join(lines)
    
    async def _generate_glossary(self, semantic_data: List[Dict[str, Any]]) -> str:
        """
        용어집 생성
        
        Args:
            semantic_data: 의미 데이터 목록
            
        Returns:
            마크다운 형식의 용어집
        """
        # 용어집 데이터 필터링
        glossary_items = [item for item in semantic_data if item["type"] == "glossary"]
        
        # 용어집 항목이 없으면 참조 데이터 사용
        if not glossary_items:
            glossary_items = [item for item in semantic_data if item["type"] == "reference"]
        
        if not glossary_items:
            return "# 용어집\n\n용어 데이터가 없습니다."
        
        # 용어를 정렬하기 위한 함수
        def get_sort_key(item):
            term = item.get("term") or item.get("content", "")
            return term.lower()
        
        # 용어 알파벳순 정렬
        sorted_glossary = sorted(glossary_items, key=get_sort_key)
        
        # 용어별로 그룹화 (한글 초성 또는 알파벳 첫 글자 기준)
        groups = {}
        
        for item in sorted_glossary:
            term = item.get("term") or item.get("content", "")
            if not term:
                continue
                
            # 첫 글자의 초성 또는 알파벳 추출
            if re.match(r'[가-힣]', term[0]):
                first_char = self._get_korean_consonant(term[0])
            elif term[0].isalpha():
                first_char = term[0].upper()
            elif term[0].isdigit():
                first_char = '0-9'
            else:
                first_char = '#'
            
            if first_char not in groups:
                groups[first_char] = []
            groups[first_char].append(item)
        
        # 마크다운 생성
        md_content = ["# 용어집\n"]
        
        # 용어 유형별로 분리
        service_terms = [item for item in sorted_glossary if item.get("term_type") == "service"]
        development_terms = [item for item in sorted_glossary if item.get("term_type") == "development"]
        design_terms = [item for item in sorted_glossary if item.get("term_type") == "design"]
        marketing_terms = [item for item in sorted_glossary if item.get("term_type") == "marketing"]
        etc_terms = [item for item in sorted_glossary if item.get("term_type") == "etc"]
        
        # 서비스 용어
        if service_terms:
            md_content.append("## 서비스 용어\n")
            md_content.append("서비스와 관련된 핵심 용어들입니다.\n")
            
            for item in service_terms:
                self._append_term_content(md_content, item)
        
        # 개발 용어
        if development_terms:
            md_content.append("\n## 개발 용어\n")
            md_content.append("개발 및 기술과 관련된 용어들입니다.\n")
            
            for item in development_terms:
                self._append_term_content(md_content, item)
        
        # 디자인 용어
        if design_terms:
            md_content.append("\n## 디자인 용어\n")
            md_content.append("디자인과 관련된 용어들입니다.\n")
            
            for item in design_terms:
                self._append_term_content(md_content, item)
        
        # 마케팅 용어
        if marketing_terms:
            md_content.append("\n## 마케팅 용어\n")
            md_content.append("마케팅과 관련된 용어들입니다.\n")
            
            for item in marketing_terms:
                self._append_term_content(md_content, item)
        
        # 기타 용어
        if etc_terms:
            md_content.append("\n## 기타 용어\n")
            md_content.append("기타 분류의 용어들입니다.\n")
            
            for item in etc_terms:
                self._append_term_content(md_content, item)
        
        return "\n".join(md_content)
    
    def _append_term_content(self, md_content: List[str], item: Dict[str, Any]) -> None:
        """
        용어 내용을 마크다운 형식으로 추가
        
        Args:
            md_content: 마크다운 내용 리스트
            item: 용어 항목
        """
        term = item.get("term") or item.get("content", "")
        definition = item.get("definition", "")
        confidence = item.get("confidence", "")
        needs_review = item.get("needs_review", False)
        
        review_mark = " ⚠️ 검토 필요" if needs_review else ""
        confidence_icon = {"high": "🟢", "medium": "🟡", "low": "🔴"}.get(confidence, "")
        
        # 대체 정의가 있는 경우
        alt_definitions = item.get("alternative_definitions", [])
        alt_def_text = ""
        if alt_definitions:
            alt_def_text += "\n\n**대체 정의:**\n"
            for i, alt_def in enumerate(alt_definitions, 1):
                alt_def_text += f"{i}. {alt_def}\n"
        
        # 키워드가 있는 경우
        keywords = item.get("keywords", [])
        keywords_text = ""
        if keywords:
            keywords_text += "\n\n**키워드:** " + ", ".join(keywords)
        
        # 도메인 힌트가 있는 경우
        domain_hints = item.get("domain_hints", [])
        domain_text = ""
        if domain_hints:
            domain_text += "\n\n**관련 분야:** " + ", ".join(domain_hints)
        
        md_content.append(f"### {term} {confidence_icon}{review_mark}\n\n{definition}{alt_def_text}{keywords_text}{domain_text}\n")
    
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