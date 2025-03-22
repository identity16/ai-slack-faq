"""
Markdown Document Generator

시맨틱 데이터를 Markdown 형식의 문서로 변환하는 모듈입니다.
"""

import os
from typing import Dict, Any, List
from datetime import datetime

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
        """용어집 생성"""
        # 기존: 참조 데이터를 사용하여 용어집 생성
        # references = [d for d in semantic_data if d["type"] == "reference"]
        
        # 수정: GLOSSARY 타입의 데이터를 사용하여 용어집 생성
        glossary_items = [d for d in semantic_data if d["type"] == "glossary"]
        
        if not glossary_items:
            # GLOSSARY 타입 데이터가 없으면 참조 데이터로 대체
            glossary_items = [d for d in semantic_data if d["type"] == "reference"]
        
        # 용어 이름 기준으로 알파벳순 정렬
        glossary_items.sort(key=lambda x: x.get("term", x.get("content", "")).lower())
        
        lines = [
            "# 용어집",
            f"\n_마지막 업데이트: {datetime.now().strftime('%Y-%m-%d %H:%M')}_\n",
            "\n용어와 정의를 알파벳순으로 정리한 문서입니다.\n"
        ]
        
        current_letter = None
        for item in glossary_items:
            # 용어가 term 필드에 있거나 content 필드에 있을 수 있음
            term = item.get("term", item.get("content", ""))
            if not term:
                continue
                
            # 첫 글자 추출 (한글, 영문, 숫자 등 모두 고려)
            first_letter = term[0].upper()
            
            # 한글인 경우 자음으로 분류
            if '가' <= first_letter <= '힣':
                consonant = self._get_korean_consonant(first_letter)
                first_letter = consonant
            
            # 숫자인 경우 '#'으로 분류
            if '0' <= first_letter <= '9':
                first_letter = '#'
            
            # 특수문자인 경우 '_'로 분류
            if not first_letter.isalnum():
                first_letter = '_'
            
            # 새로운 문자로 시작하는 섹션 추가
            if first_letter != current_letter:
                current_letter = first_letter
                lines.append(f"\n## {current_letter}\n")
            
            # 용어와 정의 추가
            definition = item.get("definition", item.get("description", ""))
            confidence = item.get("confidence", "")
            
            lines.append(f"### {term}\n")
            
            if definition:
                lines.append(f"{definition}\n")
            
            # 대안적 정의가 있는 경우 추가
            if "alternative_definitions" in item and item["alternative_definitions"]:
                lines.append("\n대안적 정의:")
                for idx, alt_def in enumerate(item["alternative_definitions"], 1):
                    lines.append(f"{idx}. {alt_def}")
                lines.append("")
            
            # 키워드 추가
            if "keywords" in item and item["keywords"]:
                lines.append(f"**관련 키워드**: {', '.join(item['keywords'])}\n")
            
            # 도메인 힌트 추가
            if "domain_hint" in item and item["domain_hint"]:
                lines.append(f"**관련 도메인**: {item['domain_hint']}\n")
            
            # 검토 필요 여부 표시
            if item.get("needs_review", False):
                lines.append(f"*이 용어의 정의는 검토가 필요합니다.*\n")
        
        return "\n".join(lines)
    
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