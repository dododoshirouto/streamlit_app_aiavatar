// getMyMemo.gs

function test() {
  let headers = getMyMemoHeadersList();
  let res = getMyMemoBlock(headers[0]);
  Logger.log(JSON.stringify(res));
}

/**
 * Webアプリとして外部からのGETリクエストを処理するメイン関数。
 * URLのパラメータに応じて、実行する関数を振り分ける。
 * @param {Object} e - Webアプリが受け取るイベントオブジェクト。e.parameterにURLパラメータが格納される。
 * @returns {ContentService.TextOutput} JSON形式のレスポンス。
 */
function doGet(e) {
  // AIからのリクエスト（URLパラメータ）を取得
  const action = e.parameter.action;
  let resultData;
  let status = "success";

  try {
    // actionの値に応じて処理を分岐
    switch (action) {
      case 'listHeaders':
        resultData = getMyMemoHeadersList();
        break;
      
      case 'getBlocks':
        const headers = JSON.parse(e.parameter.headers);
        if (!headers?.length) {
          throw new Error("パラメータ 'headers' が指定されていません。");
        }
        resultData = headers.map(header=>getMyMemoBlock(header));
        break;
        
      default:
        throw new Error("無効なactionが指定されました。'listHeaders' または 'getBlocks' を使用してください。");
    }
  } catch (error) {
    status = "error";
    resultData = { message: error.message };
  }
  
  // 結果をJSON形式で整形して返す
  const response = {
    status: status,
    data: resultData
  };
  
  return ContentService.createTextOutput(JSON.stringify(response, null, 2))
    .setMimeType(ContentService.MimeType.JSON);
}

const DOCS_URL = "https://docs.google.com/document/d/1tzRpV9pQoT9PAWOX2OkcvkEUoyylSYLa-FKM9X_AHB8/edit?tab=t.0";

function getMyMemo() {
  let doc = DocumentApp.openByUrl(DOCS_URL);
  let doc_md = doc.getAs("text/markdown");
  return doc_md.getDataAsString();
}

const HEADING_LEVEL_2_MARKDOWN = {
  HEADING1: "# ",
  HEADING2: "## ",
  HEADING3: "### ",
  HEADING4: "#### ",
  HEADING5: "##### ",
  HEADING6: "###### ",
}
/**
 * @description Googleドキュメント内の全ての見出しを階層と共に取得します。AIが最初に呼び出す「目次」取得用の関数です。
 * @returns {Array<string>} 見出しのテキストをマークダウン形式にしたもののリスト
 */
function getMyMemoHeadersList() {
  try {
    const doc = DocumentApp.openByUrl(DOCS_URL);
    const body = doc.getBody();
    const numChildren = body.getNumChildren();
    const headings = [];

    for (let i = 0; i < numChildren; i++) {
      const child = body.getChild(i);
      if (child.getType() === DocumentApp.ElementType.PARAGRAPH) {
        const paragraph = child.asParagraph();
        const headingType = paragraph.getHeading();
        
        // 見出し(Normal以外)で、かつ空でなければリストに追加
        if (headingType !== DocumentApp.ParagraphHeading.NORMAL && paragraph.getText() !== "") {
          // headings.push({
          //   level: headingType.toString(),
          //   text: paragraph.getText()
          // });
          headings.push(HEADING_LEVEL_2_MARKDOWN[headingType.toString()] + paragraph.getText());
        }
      }
    }
    return headings;
  } catch (e) {
    console.error("getMyMemoHeadersListでエラー: " + e.toString());
    return [];
  }
}

/**
 * @description 指定された見出し(テキスト)から、次の同レベル以上の見出しが出現するまでの内容を全て取得します。
 * @param {string} headerText - getMyMemoHeadersListで取得した、内容を取得したい見出しの正確なテキスト。
 * @returns {string} 指定された見出しのセクションに含まれる全てのテキスト。見つからない場合は空の文字列を返します。
 */
function getMyMemoBlock(headerText) {
  headerText = headerText.replace(/^#+ /, '');
  try {
    const doc = DocumentApp.openByUrl(DOCS_URL);
    const body = doc.getBody();
    const numChildren = body.getNumChildren();
    let content = [];
    let isCapturing = false;
    let startHeadingLevel = null;

    for (let i = 0; i < numChildren; i++) {
      const child = body.getChild(i);
      const childType = child.getType();

      // 要素が段落(Paragraph)の場合の処理
      if (childType === DocumentApp.ElementType.PARAGRAPH) {
        const paragraph = child.asParagraph();
        
        if (!isCapturing) {
          // 目的の見出しを見つけたらキャプチャを開始
          if (paragraph.getText() === headerText && paragraph.getHeading() !== DocumentApp.ParagraphHeading.NORMAL) {
            isCapturing = true;
            startHeadingLevel = paragraph.getHeading();
          }
        } else {
          // キャプチャ中に次の見出しを見つけたか判定
          const currentHeading = paragraph.getHeading();
          if (currentHeading !== DocumentApp.ParagraphHeading.NORMAL && currentHeading <= startHeadingLevel) {
            // 次の同レベル以上の見出しに到達したので、キャプチャを終了
            break; 
          }
          content.push(paragraph.getText());
        }
      } 
      // 段落以外の要素(リスト項目など)の処理
      else if (isCapturing && (childType === DocumentApp.ElementType.LIST_ITEM || childType === DocumentApp.ElementType.TABLE)) {
        content.push(child.asText().getText());
      }
    }
    return content.join('\n');
  } catch (e) {
    console.error("getMyMemoBlockでエラー: " + e.toString());
    return "";
  }
}