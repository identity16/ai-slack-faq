#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
용어집 문서 생성 예제
"""

import os
import asyncio
from typing import Dict, Any, List

from src.document import DocumentGenerator, DocumentType
from src.document.generators import MarkdownGenerator, HTMLGenerator
from src.semantic_data import LLMClient, SlackExtractor, SemanticType
from src.semantic_data import enhance_low_confidence_terms


async def main():
    # 예시 데이터 정의
    example_data = {
        "messages": [
            {
                "text": "CI/CD 파이프라인은 개발자가 코드를 빠르고 안정적으로 배포할 수 있게 도와주는 자동화 프로세스입니다."
            },
            {
                "text": "API는 Application Programming Interface의 약자로, 서로 다른 소프트웨어 시스템이 통신할 수 있게 하는 인터페이스입니다."
            },
            {
                "text": "React는 페이스북에서 개발한 자바스크립트 라이브러리로, 사용자 인터페이스를 구축하기 위한 도구입니다."
            },
            {
                "text": "Admin Board 시스템은 우리 회사에서 관리자가 사용자 데이터를 관리하고 통계를 확인하는 내부 대시보드입니다."
            },
            {
                "text": "우리 팀은 퍼플북 문서에 모든 시스템 설계와 아키텍처 정보를 기록하고 있어요."
            },
            {
                "text": "신규 엔진은 회사에서 개발 중인 차세대 추천 시스템으로, 기존 시스템보다 더 정확한 추천을 제공합니다."
            },
            {
                "text": "ROAS 대시보드에서 우리 마케팅 캠페인의 투자 수익률을 추적하고 있습니다."
            },
            {
                "text": "AM 미팅은 매주 월요일 오전에 진행되는 계정 관리팀의 주간 업무 점검 회의입니다."
            },
            {
                "text": "TDD 프로세스는 우리 개발팀이 모든 신규 기능 개발에 적용하는 테스트 주도 개발 방법론입니다."
            },
            {
                "text": "iSDK는 우리 회사가 파트너들에게 제공하는 통합 소프트웨어 개발 키트로, API 연동을 쉽게 할 수 있습니다."
            }
        ]
    }

    # LLM 클라이언트 초기화
    openai_api_key = os.environ.get("OPENAI_API_KEY")
    llm_client = LLMClient(api_key=openai_api_key)

    # Slack 추출기 초기화 및 데이터 처리
    extractor = SlackExtractor(llm_client=llm_client)
    semantic_data = await extractor.process(example_data)

    # 용어집 항목만 필터링
    glossary_items = [item for item in semantic_data if item["type"] == SemanticType.GLOSSARY]
    
    # 낮은 확신도의 용어 개선
    enhanced_glossary = await enhance_low_confidence_terms(glossary_items, llm_client)
    
    # 문서 생성기 초기화
    md_generator = MarkdownGenerator()
    html_generator = HTMLGenerator()
    
    # 마크다운 문서 생성 및 저장
    md_content = await md_generator.generate(enhanced_glossary, DocumentType.GLOSSARY)
    md_path = "examples/output/glossary.md"
    os.makedirs(os.path.dirname(md_path), exist_ok=True)
    await md_generator.save(md_content, md_path)
    
    # HTML 문서 생성 및 저장
    html_content = await html_generator.generate(enhanced_glossary, DocumentType.GLOSSARY)
    html_path = "examples/output/glossary.html"
    await html_generator.save(html_content, html_path)
    
    print(f"생성된 파일:")
    print(f"- {md_path}")
    print(f"- {html_path}")


if __name__ == "__main__":
    asyncio.run(main()) 