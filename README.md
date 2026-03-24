# kanji-gime

研究室や班の代表候補をその場で入力し、隠していた評価基準を最後に公開したうえで Gemini API に判定させる CLI ツールです。

## 動作環境

- Python 3.11

## セットアップ

1. `.env.example` を参考に `.env` を作成します。
2. `GEMINI_API_KEY` に Gemini API のキーを設定します。
3. 必要なら `GEMINI_MODEL` を変更します。未設定時は `gemini-2.0-flash` を使います。

`.env` の例:

```env
GEMINI_API_KEY=your_api_key_here
GEMINI_MODEL=gemini-2.0-flash
```

API キーは環境変数から読み込むため、コード内に秘密情報を直書きする必要はありません。

## 評価基準の管理

評価基準は `criteria.json` で管理します。トップレベルの `criteria` 配列に、各基準を次の形式で記述します。

- `id`: 内部識別子
- `title`: 表示名
- `description`: 評価内容の説明
- `weight`: 重み

例:

```json
{
  "criteria": [
    {
      "id": "leadership",
      "title": "主体性",
      "description": "代表として自分から動き、周囲を前向きに巻き込めそうかを評価する。",
      "weight": 5
    }
  ]
}
```

## 実行方法

```bash
python main.py
```

実行すると次の流れで動きます。

1. 候補名と意気込みを複数件入力する
2. 入力終了後に評価基準を表示する
3. Gemini に送る最終プロンプト全文を表示する
4. Gemini の返答から以下を表示する

- 選出候補
- 理由
- 次点へのコメント
