import os
import traceback
import subprocess
from flask import Flask, request, jsonify, render_template
from werkzeug.utils import secure_filename
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.config["UPLOAD_FOLDER"] = "uploads"
app.config["MAX_CONTENT_LENGTH"] = 25 * 1024 * 1024  # 25MB

ALLOWED_EXTENSIONS = {"mp3", "wav", "m4a"}

# APIキーの確認
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    raise ValueError(
        "❌ エラー: OPENAI_API_KEY が設定されていません。\n"
        "1. .env ファイルを作成して以下を記入してください：\n"
        "   OPENAI_API_KEY=sk-...\n"
        "2. または、コマンドラインから以下を実行：\n"
        "   export OPENAI_API_KEY='sk-...'\n"
        "詳しくは README.md の「.env の設定方法」をご覧ください。"
    )

client = OpenAI(api_key=api_key)


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def convert_m4a_to_mp3(file_path):
    """m4aをmp3に変換する（ffmpegを使用）"""
    if not file_path.endswith('.m4a'):
        return file_path, False
    
    try:
        mp3_path = file_path.replace('.m4a', '.mp3')
        subprocess.run(
            ['ffmpeg', '-i', file_path, '-q:a', '9', '-map', 'a', mp3_path],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=True
        )
        return mp3_path, True
    except subprocess.CalledProcessError as e:
        raise Exception(f"m4a→mp3変換エラー: ffmpegコマンド実行に失敗しました")
    except FileNotFoundError:
        raise Exception(f"m4a→mp3変換エラー: ffmpegがインストールされていません")


def transcribe_audio(file_path):
    # m4aをmp3に変換
    converted_path, is_converted = convert_m4a_to_mp3(file_path)
    
    try:
        with open(converted_path, "rb") as audio_file:
            response = client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                language="ja",
            )
        return response.text
    finally:
        # 変換されたファイルを削除
        if is_converted and os.path.exists(converted_path):
            os.remove(converted_path)


def generate_minutes(transcription):
    prompt = f"""以下の会議の文字起こしをもとに、議事録を作成してください。
必ず以下のフォーマットで出力してください。

【会議タイトル】
会議内容から自然なタイトルを1つ作成する。
音声認識の誤りがある場合は、会議全体の文脈から明らかに自然な表現に補正してください。
例：「AI26アプリ」→「AI議事録アプリ」、「ReadMeファイル」→「READMEファイル」のように補正します。

【要約】
会議全体の内容を3〜5行で簡潔にまとめる。

【決定事項】
会議内で決定した方針・仕様・判断を箇条書きでまとめてください。
これは「会議で何が決まったか」です。
・仕様の決定
・方針の決定
・判断基準の決定
・実装方法の方向性決定
など
決定事項がない場合は「特になし」と書く。

【ToDo】
「会議後に誰かが実行すべき具体的な作業」だけを入れてください。
以下のすべてに当てはまるもののみToDoです：
1. 会議内で明示された作業である（推測で追加しない）
2. 「〇〇する」「〇〇を作る」「〇〇を修正する」など、具体的で実行可能な作業である
3. 会議で話題になった内容である

ToDoに入れてはいけません：
・推測で便利そうだと思う作業（→入れない）
・単なる仕様の決定（→決定事項へ）
・方針の説明（→決定事項へ）
・実装済みの内容
・会議中に確認しただけの内容
・担当者も期限もなく、具体的な作業として弱い内容
・会議で明示されていない作業

【重要：ToDoは最大3件です】
会議後に実行すべき重要タスクのみを抽出してください。
細かすぎる作業は1つにまとめてください。
決めるべき内容がない場合は「特になし」と出力してください。

ToDoがある場合、以下のフォーマットで厳密に統一してください：

・担当者：〇〇
  内容：〇〇
  期限：〇〇

※担当者や期限が不明な場合は「未定」と記入
※「次回の会議まで」など文脈から期限が明確な場合は「次回まで」と記入可
※文字起こしにない担当者や期限を勝手に作らないでください
※必ず「・」で始まり、2行目以降は「  」（スペース2つ）でインデント
※ToDoが1〜3件：その件数だけ出力
※ToDoが明確にない場合は「特になし」と出力してください。

【次回確認事項】
・次回の会議や作業前に確認すべき内容を箇条書きでまとめる。
・決定事項やToDoとして弱い内容、確認待ちの項目もここに入る
・ない場合は「特になし」と書く。

【懸念点】
・リスクや未解決の問題を箇条書きでまとめる。
・ない場合は「特になし」と書く。

【重要：表記統一ルール】
議事録全体で以下の表記に必ず統一してください。出力前に全文をチェックしてください：
- ReadMe / Readme / readme → README
- Github / Git hub / github / ギットハブ → GitHub
- To Do / todo / TODO / ToDoリスト → ToDo
- MVP / エมวぴ → MVP- オープンAPI / オープンAI / OAI → OpenAI API（文脈で判断）- AI26アプリ / AI議事録アプリケーション → AI議事録アプリ
- その他の音声認識による不自然な語 → 文脈上自然な語に統一

【補正の原則】
1. 文脈から明らかに間違っている誤認識のみ補正する
2. 文字起こしに書かれていない新しい情報を追加しない
3. 補正なしでも意味が通じる場合は補正しない
4. 技術用語や固有名詞は正しい表記に統一する
5. 文字起こしにない担当者や期限は作らない

--- 文字起こし ---
{transcription}
"""
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "system",
                "content": """あなたは優秀なビジネスアシスタントです。会議の文字起こしから、実務で使える正確で読みやすい議事録を作成してください。

【最優先事項】
1. 音声認識による誤りを文脈から推測して自然に補正する
2. 技術用語や固有名詞を正しい表記に統一する
3. 表記ゆれを徹底的に統一する（OpenAI APIなど）
4. ToDoは指定のフォーマットに厳密に従う

【重要：決定事項とToDoの区別】
決定事項：「会議で何が決まったか」（方針・仕様・判断）
例：「ユーザー認証にAzure ADを使う」「レスポンスタイムを1秒以下にする」

ToDo：「会議後に誰かが実行すべき具体的な作業」
例：「AさんがAzure AD連携を実装する」「Bさんが次回会議までにプロトタイプを作成する」

・推測で便利そうな作業を追加しない
・会議で明示されていない内容はToDoにしない
・ToDoは最大3件
・決めるべき内容がない場合は「特になし」

【禁止事項】
- 文字起こしにない情報を捏造する
- 文字起こしにない担当者や期限を作る
- 推測で新しい情報を追加する
- 会議で明示されていない作業をToDoにする
- 不確実な補正をする

【会議タイトルについて】
特に重要です。「AI26アプリの開発方針について」ではなく、文脈から自然な「AI議事録アプリの開発方針について」という形にしてください。

【出力前チェックリスト】
□ 決定事項とToDoは明確に分けられているか
□ ToDoは会議で明示された内容のみか
□ ToDoは最大3件か
□ 推測で追加された作業はないか
□ 担当者や期限は文字起こしから取られているか
□ 表記ゆれはすべて統一されているか
□ 新しい情報は追加されていないか
□ 会議タイトルは自然な日本語か""",
            },
            {"role": "user", "content": prompt},
        ],
        temperature=0.3,
    )
    return response.choices[0].message.content


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/upload", methods=["POST"])
def upload():
    if "audio" not in request.files:
        return jsonify({"error": "ファイルが選択されていません。"}), 400

    file = request.files["audio"]

    if file.filename == "":
        return jsonify({"error": "ファイルが選択されていません。"}), 400

    if not allowed_file(file.filename):
        return jsonify({"error": "対応していないファイル形式です。mp3 / wav / m4a をアップロードしてください。"}), 400

    filename = secure_filename(file.filename)
    file_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)

    try:
        file.save(file_path)
        transcription = transcribe_audio(file_path)
        minutes = generate_minutes(transcription)
        return jsonify({"transcription": transcription, "minutes": minutes})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": f"AI処理中にエラーが発生しました: {str(e)}"}), 500
    finally:
        if os.path.exists(file_path):
            os.remove(file_path)


if __name__ == "__main__":
    app.run(debug=True, port=5001)
