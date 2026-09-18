# AI Monitor

macOS 메뉴 막대에서 AI 구독 사용 한도와 API 잔액을 확인하세요.

[English](../../README.md) · [简体中文](../../README.zh-CN.md) · [繁體中文](README.zh-TW.md) · [日本語](README.ja.md) · **한국어** · [Español](README.es.md) · [Français](README.fr.md) · [Deutsch](README.de.md) · [Português](README.pt-BR.md)

**[Mac용 다운로드](https://github.com/Neptuneeeeeeee/AI-Monitor/releases/download/v1.9.4/AI-Monitor-v1.9.4-macos-arm64.dmg)** · [ZIP 파일](https://github.com/Neptuneeeeeeee/AI-Monitor/releases/download/v1.9.4/AI-Monitor-v1.9.4-macos-arm64.zip) · [릴리스 노트](https://github.com/Neptuneeeeeeee/AI-Monitor/releases/tag/v1.9.4)

**Apple Silicon(M 시리즈) · macOS 14 이상 · Python 포함**

DMG를 열고 **AI Monitor.app**을 **응용 프로그램**으로 드래그한 다음, 설정에서 표시할 서비스를 선택하세요. Python, Xcode, Homebrew를 따로 설치할 필요는 없습니다. 일부 서비스는 공식 클라이언트와 로그인이 필요합니다.

> **미리 보기 버전:** Developer ID 서명과 Apple 공증이 적용되지 않았습니다. 처음 실행할 때 macOS가 차단할 수 있으므로 [설치 안내](../INSTALL.md)를 읽고 출처를 확인한 뒤 실행 여부를 결정하세요. 시스템 전체의 보안 기능을 끄지 마세요.

![AI Monitor 사용 한도, 설정 및 API 잔액](../images/en/hero.png)

*이미지의 수치는 모두 예시입니다. v1.9.4 앱 화면은 주로 중국어이며, 영어 이미지는 문서용 번역 미리 보기입니다. 위의 언어 링크는 README만 전환합니다.*

## 주요 기능

- 남은 사용 한도와 초기화 시간을 확인하고 메뉴 막대에 흑백 막대로 표시합니다.
- 표시할 구독 서비스를 선택하고 원하는 순서로 정렬합니다.
- 서비스에서 제공하는 API 잔액 또는 당일 비용 화면으로 전환합니다.

## 지원 서비스

**구독 서비스:** Claude · Codex · Kimi · GitHub Copilot · Antigravity · Cursor · GLM · MiniMax · Windsurf · Kiro

**API 연결:** DeepSeek · Kimi · OpenAI · Claude · SiliconFlow · OpenRouter. Google AI Studio는 접근 권한 확인만 지원하며 청구 금액은 표시하지 않습니다.

표시 가능한 정보는 서비스와 계정에 따라 다릅니다. Windsurf는 실시간 데이터가 아닌 로컬 캐시를 표시합니다. 제한 사항과 연결 요건은 [지원 기능 안내](../PROVIDER_CAPABILITIES.md)를 확인하세요.

<details>
<summary>화면 더 보기</summary>

<p>
<img src="../images/en/plans.png" alt="구독 사용 한도 예시" width="31%">
<img src="../images/en/settings.png" alt="서비스 선택 및 정렬" width="31%">
<img src="../images/en/api-balance.png" alt="API 잔액 및 비용 예시" width="31%">
</p>

</details>

[설치 안내](../INSTALL.md) · [지원 기능](../PROVIDER_CAPABILITIES.md) · [개인정보 안내](../../PRIVACY.md) · [변경 기록](../../CHANGELOG.md) · [소스에서 빌드](../DEVELOPMENT.md)

소스 코드 라이선스는 아직 선정되지 않았습니다. [라이선스 안내](../../LICENSE_PENDING.md)와 [타사 고지](../../THIRD_PARTY_NOTICES.md)를 확인하세요.
