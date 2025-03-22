#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
용어집 문서 생성 예제
"""

import os
import asyncio
from typing import List, Dict, Any

from src.semantic_data import GlossaryExtractor, enhance_low_confidence_terms
from src.document import DocumentGenerator, DocumentType
from src.document.generators import MarkdownGenerator, HTMLGenerator


async def generate_glossary_documents(glossary_data: List[Dict[str, Any]], output_dir: str):
    """
    용어집 데이터를 사용하여 마크다운 및 HTML 형식의 용어집 문서를 생성합니다.
    
    Args:
        glossary_data: 용어집 데이터 리스트
        output_dir: 출력 디렉토리 경로
    """
    # 출력 디렉토리가 없는 경우 생성
    os.makedirs(output_dir, exist_ok=True)
    
    # Markdown 생성기를 사용하여 마크다운 문서 생성
    md_generator = MarkdownGenerator()
    md_content = await md_generator.generate(glossary_data, DocumentType.GLOSSARY)
    md_file_path = os.path.join(output_dir, "glossary.md")
    
    # HTML 생성기를 사용하여 HTML 문서 생성
    html_generator = HTMLGenerator()
    html_content = await html_generator.generate(glossary_data, DocumentType.GLOSSARY)
    html_file_path = os.path.join(output_dir, "glossary.html")
    
    # 파일로 저장
    with open(md_file_path, "w", encoding="utf-8") as f:
        f.write(md_content)
    print(f"마크다운 용어집 생성 완료: {md_file_path}")
    
    with open(html_file_path, "w", encoding="utf-8") as f:
        f.write(html_content)
    print(f"HTML 용어집 생성 완료: {html_file_path}")
    
    return md_file_path, html_file_path


async def extract_and_generate_glossary(data: Dict[str, Any], output_dir: str):
    """
    데이터에서 용어집을 추출하고 문서를 생성합니다.
    
    Args:
        data: 용어집을 추출할 데이터
        output_dir: 출력 디렉토리 경로
    """
    # GlossaryExtractor를 사용하여 용어집 추출
    extractor = GlossaryExtractor()
    semantic_data = await extractor.extract(data)
    
    # 신뢰도가 낮은 용어에 대한 추가 처리
    enhanced_data = await enhance_low_confidence_terms(semantic_data)
    
    # 용어집 문서 생성
    return await generate_glossary_documents(enhanced_data, output_dir)


async def main():
    """
    예제 실행 함수
    """
    # 예제 데이터 (실제 사용 시에는 실제 데이터로 대체)
    example_data = {
        "messages": [
            {
                "text": "API란 Application Programming Interface의 약자로, 소프트웨어 간의 통신을 위한 인터페이스입니다.",
                "user": "U12345",
                "ts": "1610000000.000000"
            },
            {
                "text": "CI/CD는 Continuous Integration/Continuous Deployment의 약자로, 지속적 통합 및 배포를 의미합니다.",
                "user": "U67890",
                "ts": "1610000100.000000"
            },
            {
                "text": "React는 페이스북에서 개발한 사용자 인터페이스를 구축하기 위한 JavaScript 라이브러리입니다.",
                "user": "U12345",
                "ts": "1610000200.000000"
            },
            {
                "text": "TDD는 Test Driven Development의 약자로, 테스트 주도 개발을 의미합니다.",
                "user": "U67890",
                "ts": "1610000300.000000"
            },
            {
                "text": "SDK는 Software Development Kit의 약자로, 특정 플랫폼을 위한 개발 도구 모음을 의미합니다.",
                "user": "U12345",
                "ts": "1610000400.000000"
            }
        ]
    }
    
    # 출력 디렉토리
    output_dir = "output"
    
    # 용어집 추출 및 문서 생성
    md_file, html_file = await extract_and_generate_glossary(example_data, output_dir)
    
    print(f"\n생성된 파일:")
    print(f"- 마크다운: {md_file}")
    print(f"- HTML: {html_file}")


if __name__ == "__main__":
    asyncio.run(main()) 