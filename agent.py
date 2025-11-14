import os
import sys
from typing import Optional
from openai import AzureOpenAI
from dotenv import load_dotenv

# UTF-8エンコーディングを強制（Windows環境のみ）
if sys.platform == 'win32':
    try:
        import codecs
        sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
        sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')
    except Exception:
        pass  # Azure App Service等のLinux環境では不要

load_dotenv()

class KousuAgent:
    def __init__(self, database):
        self.db = database
        endpoint = os.getenv('AZURE_OPENAI_ENDPOINT')
        api_key = os.getenv('AZURE_OPENAI_API_KEY')
        deployment = os.getenv('AZURE_OPENAI_DEPLOYMENT_NAME')
        api_version = os.getenv('AZURE_OPENAI_API_VERSION', '2024-02-15-preview')

        if endpoint and api_key and deployment:
            self.client = AzureOpenAI(
                azure_endpoint=endpoint,
                api_key=api_key,
                api_version=api_version
            )
            self.deployment_name = deployment
            self.enabled = True
        else:
            self.client = None
            self.deployment_name = None
            self.enabled = False

    def chat(self, message: str, year: Optional[int] = None, month: Optional[int] = None) -> str:
        if not self.enabled:
            return "エージェント機能を使用するには、.envファイルにAzure OpenAIの設定を行ってください。"

        kousu_data = self.db.get_summary_by_period(year, month)

        period_str = "全期間"
        if year and month:
            period_str = f"{year}年{month}月"
        elif year:
            period_str = f"{year}年"

        system_prompt = """あなたは工数管理の専門家です。以下の工数データを基に、ユーザーの質問に答えてください。

回答の際は、以下の点に注意してください：
1. 見やすさのため、適切に改行を入れてください
2. 箇条書きや段落分けを活用してください
3. 数値データを提示する際は表形式や箇条書きにしてください
4. 重要なポイントは太字(**テキスト**)や見出しで強調してください"""

        user_content = f"""
【対象期間】: {period_str}

【工数サマリー】:
- 見積工数合計: {kousu_data['total_estimated']:.1f}時間
- 予定工数合計: {kousu_data['total_planned']:.1f}時間
- 実績工数合計: {kousu_data['total_actual']:.1f}時間
- 案件・レコード数: {kousu_data['record_count']}件

【詳細データ】:
"""
        for record in kousu_data['records']:
            user_content += f"\n案件: {record['project_name']}"
            if record['client']:
                user_content += f" (クライアント: {record['client']})"
            user_content += f"\n  期間: {record['year']}年{record['month']}月"

            # メンバー情報を追加
            if record.get('member_name'):
                user_content += f"\n  担当者: {record['member_name']}"
            else:
                user_content += f"\n  担当者: 未割当（案件全体）"

            user_content += f"\n  見積工数: {record['estimated_hours']:.1f}h"
            user_content += f"\n  予定工数: {record['planned_hours']:.1f}h"
            user_content += f"\n  実績工数: {record['actual_hours']:.1f}h"

            # 差分情報も追加
            estimated_diff = record['actual_hours'] - record['estimated_hours']
            planned_diff = record['actual_hours'] - record['planned_hours']
            user_content += f"\n  見積差分: {estimated_diff:+.1f}h"
            user_content += f"\n  予定差分: {planned_diff:+.1f}h"

            if record['notes']:
                user_content += f"\n  備考: {record['notes']}"
            user_content += "\n"

        user_content += f"\n【ユーザーの質問】: {message}"

        try:
            print(f"[DEBUG] Calling Azure OpenAI with model: {self.deployment_name}")
            print(f"[DEBUG] API Version: {self.client._api_version}")

            response = self.client.chat.completions.create(
                model=self.deployment_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content}
                ],
                max_completion_tokens=4000
            )

            print(f"[DEBUG] Response received")
            print(f"[DEBUG] Response.choices: {response.choices}")
            print(f"[DEBUG] First choice: {response.choices[0]}")
            print(f"[DEBUG] Message: {response.choices[0].message}")
            print(f"[DEBUG] Message.content: {repr(response.choices[0].message.content)}")

            result = response.choices[0].message.content
            print(f"[DEBUG] Result assigned, length: {len(result) if result else 0}")
            print(f"[DEBUG] Result type: {type(result)}")
            print(f"[DEBUG] Result repr: {repr(result[:100]) if result else 'None'}")

            if not result or len(result.strip()) == 0:
                print("[ERROR] Empty response from API")
                return "応答が空でした。もう一度お試しください。"

            print(f"[DEBUG] Returning result of length {len(result)}")
            return result

        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            print(f"[ERROR] {error_details}")
            return f"エラーが発生しました: {str(e)}"
