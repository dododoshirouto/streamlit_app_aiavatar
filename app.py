from datetime import datetime
import json
import requests
import streamlit as st
from streamlit_oauth import OAuth2Component # ライブラリをインポート

import base64
import os
from google import genai
from google.genai import types



DEBUG_SKIP_OAUTH = st.secrets.get("DEBUG_SKIP_OAUTH", "false")=="true"
DEBUG_USE_LITE_MODEL = st.secrets.get("DEBUG_USE_LITE_MODEL", "true")=="true"



@st.cache_data # このおまじないを追加
def load_prompt(file_path="system_prompt.txt"):
    """プロンプトファイルを読み込んで、その内容を返す関数"""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        st.error(f"`{file_path}` が見つかりません。")
        return "あなたは優秀なアシスタントです。"

SYSTEM_PROMPT = load_prompt()
MY_AVATAR = "https://pbs.twimg.com/profile_images/1891699361610072066/i3JVHI8G_400x400.jpg"
MY_NAME = "どどど素人(Kazuki Fukunaga) AI"
PRE_HISTORY_SIZE = 3
MAX_HISTORY_SIZE = 10

# --- 認証情報の設定 (StreamlitのSecretsから読み込む) ---
CLIENT_ID = st.secrets.get("GOOGLE_CLIENT_ID")
CLIENT_SECRET = st.secrets.get("GOOGLE_CLIENT_SECRET")
REDIRECT_URI = st.secrets.get("GOOGLE_REDIRECT_URI") # Google Cloudで設定したリダイレクトURI
AUTHORIZE_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
REVOKE_ENDPOINT = "https://oauth2.googleapis.com/revoke"
GEMINI_API_KEY = st.secrets.get("GEMINI_API_KEY")

# --- 会社のドメインを指定 ---
REQUIRED_DOMAIN = st.secrets.get("REQUIRED_DOMAIN")

# OAuthコンポーネントの作成
oauth2 = OAuth2Component(CLIENT_ID, CLIENT_SECRET, AUTHORIZE_ENDPOINT, TOKEN_ENDPOINT, TOKEN_ENDPOINT, REVOKE_ENDPOINT)

GOOGLE_CALENDAR_GAS_URL = st.secrets.get("GOOGLE_CALENDAR_GAS_URL")
def get_google_calendar_events():
    """
    中の人（福永）のGoogleカレンダーのイベントを取得（前後1週間分）
    自分の予定のように話す
    予定を聞かれたときに使う
    MTG以外の予定は前後1時間は移動とかで対応難しいかも
    裁判関係や法律のことは言及厳禁！「予定がある」とかでぼやかして
    """
    # GASのdoGet関数を呼び出して、Googleカレンダーのイベントを取得(JSON形式で返ってくる)
    st.write(f"🔍 Googleカレンダーを取得中…")

    response = requests.get(GOOGLE_CALENDAR_GAS_URL)
    if response.status_code != 200:
        st.write(f"Googleカレンダーの取得に失敗しました: {response.status_code}")
        return f"Googleカレンダーの取得に失敗しました: {response.status_code}"

    events = response.json()

    output = []
    for event in events:
        title = event["title"]
        start = event["start"]
        end = event["end"]
        description = event["description"]
        isAllDayEvent = event["isAllDayEvent"]
        output.append(f"{title} | {(isAllDayEvent and '終日' or f'{start} - {end}')} | {description}")

    st.write(f"🔍 Googleカレンダーを取得しました")
    return output

GOOGLE_DOCS_GAS_URL = st.secrets.get("GOOGLE_DOCS_GAS_URL")
def get_google_docs_headers():
    """
    中の人（福永）の情報データのヘッダーリストを取得する
    質問来たらとりあえず取得してみる
    ユーザにはそのままじゃなくてまとめなおして回答して
    """
    st.write(f"🔍 ドキュメントの項目を取得中…")
    response = requests.get(GOOGLE_DOCS_GAS_URL, params={"action": "listHeaders"})
    if response.ok == False:
        st.write(f"Google Docsの取得に失敗しました: {response.resultData.message}")
        return f"Google Docsの取得に失敗しました: {response.resultData.message}"

    headers = response.json()
    st.write(f"🔍 ドキュメントの項目を取得しました")
    return headers['data']

def get_google_docs_contents(headers: list[str]):
    """
    中の人（福永）の情報データを取得する
    ユーザにはそのままじゃなくてまとめなおして回答して
    get_google_docs_headers()を呼び出してから使う
    Args:
        headers: 取得したい中の人（福永）の情報データのヘッダーのリスト。get_google_docs_headers()を呼び出して取得したものから正確に指定する
    """
    st.write(f"🔍 ドキュメントを取得中…：" + ",".join(headers))
    response = requests.get(GOOGLE_DOCS_GAS_URL, params={"action": "getBlocks", "headers": json.dumps(headers)})
    if response.ok == False:
        st.write(f"Google Docsの取得に失敗しました: {response.resultData.message}")
        return f"Google Docsの取得に失敗しました: {response.resultData.message}"

    contents = response.json()
    print(contents)
    st.write(f"🔍 ドキュメントを取得しました：" + ",".join(headers))
    return contents['data']

def main():
    try:
        st.title("どどど素人(Kazuki Fukunaga) AI")
        st.caption("予定とか見れるよ")
    except: pass

    # --- ログイン処理 ---
    # セッション状態からトークンを取得
    # if 'token' not in st.session_state:
    #     st.session_state.token = None

    # ログインボタンを表示
    if not (DEBUG_SKIP_OAUTH or st.user.is_logged_in):
        st.write("Googleアカウントでログインしてください。")
        st.login() # 認証フローを開始
        # if st.button("Googleアカウントでログイン", icon=":material/login:"):
        #     st.login()
        st.stop()

    # --- ログイン後の処理 ---
    # st.success("ログインに成功しました！")

    # --- ログイン後の処理 ---
    if DEBUG_SKIP_OAUTH or st.user.is_logged_in:

        if not DEBUG_SKIP_OAUTH:

            # ドメインチェック
            if st.user.email and st.user.email.endswith(f"@{REQUIRED_DOMAIN}"):
                # 会社のアカウントじゃない場合はエラー表示
                st.error(f"アクセスが許可されていません。@{REQUIRED_DOMAIN} のアカウントでログインしてください。")
                st.session_state.token = None # 不正なユーザーはログアウトさせる
                st.stop()
                exit()
                
            st.success(f"{st.user.name}さんとしてログイン中")
        else:
            class User:
                def __init__(self, name, email):
                    self.name = name
                    self.email = email
                    self.is_logged_in = True
                def get(self, key):
                    return None
            st.user = User("", f"test@{REQUIRED_DOMAIN}")
            
        st.write("---")

        # ↓↓↓ ここから下が、ログイン成功した人だけが見えるチャットアプリ本体 ↓↓↓

        # --- 2. クライアントとチャット履歴の初期化 ---

        if not GEMINI_API_KEY:
            st.error("GEMINI_API_KEYが設定されていません。環境変数を設定してください。")
            st.stop()

        tools = {
            'get_google_calendar_events': get_google_calendar_events,
            'get_google_docs_headers': get_google_docs_headers,
            'get_google_docs_contents': get_google_docs_contents,
        }
        
        # サンプルコードに準拠して、genai.Clientを初期化
        try:
            client = genai.Client(api_key=GEMINI_API_KEY)
        except Exception as e:
            st.error("Geminiクライアントの初期化に失敗しました。APIキーが正しいか確認してください。")
            st.exception(e)
            st.stop()

        if "messages" not in st.session_state:
            st.session_state.messages = []

            # 初回メッセージを生成する
            with st.chat_message(MY_NAME, avatar=MY_AVATAR):
                generate_content_config = types.GenerateContentConfig(
                    temperature=0.8,
                    top_p=0.8,
                    thinking_config = types.ThinkingConfig(
                        thinking_budget=0,
                    ),
                    system_instruction=[
                        types.Part.from_text(text=SYSTEM_PROMPT),
                    ],
                    tools=tools.values(),
                )
                response_stream = client.models.generate_content_stream(
                    model="gemini-2.5-flash" if not DEBUG_USE_LITE_MODEL else "gemini-2.5-flash-lite", # ここで使用するモデルを選択
                    contents=[types.Content(role="user", parts=[types.Part.from_text(text=f"{st.user.name}さんに挨拶して、何を聞きに来たか聞いて\n\n#current time: {datetime.now().isoformat()}\n\n#user name: {st.user.name}")])],
                    config=generate_content_config,
                )
                full_response = ""
                placeholder = st.empty()
                for chunk in response_stream:
                    full_response += chunk.text
                    placeholder.markdown(full_response + "▌")
                placeholder.markdown(full_response)
                st.session_state.messages.append({"role": "assistant", "content": full_response})

        else:
            # --- 3. チャット履歴の表示 ---
            for message in st.session_state.messages:
                with st.chat_message(
                    MY_NAME if message["role"] == "assistant" else st.user.name,
                    avatar=MY_AVATAR if message["role"] == "assistant" else st.user.get("picture"),
                    ):
                    # もし[user_input]があれば、[user_input]から[/user_input]の間を取り出す
                    prompt = message["content"].split("[user_input]")[-1].split("[/user_input]")[0]
                    st.markdown(prompt)

        # --- 4. ユーザーからのメッセージ入力と送信 ---
        if prompt := st.chat_input("何か話しかけてみて"):
            prompt_send = f"""[user_input]{prompt}[/user_input]\n\n#current time: {datetime.now().isoformat()}\n\n#user name: {st.user.name}"""
            st.session_state.messages.append({"role": "user", "content": prompt_send})
            with st.chat_message(st.user.name, avatar=st.user.get("picture")):
                st.markdown(prompt)

            with st.chat_message(MY_NAME, avatar=MY_AVATAR):
                try:
                    # --- API呼び出し部分をサンプルコードに準拠させる ---

                    # 1. チャット履歴をAPIが要求する'contents'形式に変換
                    #    AIの発言のroleは'assistant'ではなく'model'にする必要があるので注意
                    contents_for_api = []
                    for msg in st.session_state.messages:
                        role = "user" if msg["role"] == "user" else "model"
                        contents_for_api.append(types.Content(role=role, parts=[types.Part.from_text(text=msg["content"])]))
                    
                    if len(contents_for_api) > MAX_HISTORY_SIZE + PRE_HISTORY_SIZE:
                        contents_for_api = contents_for_api[:PRE_HISTORY_SIZE] + contents_for_api[-MAX_HISTORY_SIZE:]
                    
                    # 2. configオブジェクトを作成
                    generate_content_config = types.GenerateContentConfig(
                        temperature=0.8,
                        top_p=0.8,
                        thinking_config = types.ThinkingConfig(
                            thinking_budget=0,
                        ),
                        system_instruction=[
                            types.Part.from_text(text=SYSTEM_PROMPT),
                        ],
                        tools=tools.values(),
                    )

                    # 3. generate_content_streamを呼び出し
                    response_stream = client.models.generate_content_stream(
                        model="gemini-2.5-flash" if not DEBUG_USE_LITE_MODEL else "gemini-2.5-flash-lite", # ここで使用するモデルを選択
                        contents=contents_for_api,
                        config=generate_content_config,
                    )
                    
                    # 4. レスポンスをUIにストリーミング表示
                    full_response = ""
                    placeholder = st.empty()
                    for chunk in response_stream:
                        full_response += chunk.text or ''
                        placeholder.markdown(full_response + "▌")
                    placeholder.markdown(full_response)
                    
                    # 5. AIの完全な応答を履歴に追加
                    st.session_state.messages.append({"role": "assistant", "content": full_response})

                except Exception as e:
                    st.error("AIとの通信中にエラーが発生しました。")
                    st.exception(e)


    else:
        st.warning("会社のGoogleアカウントでログインしてください。")



main()