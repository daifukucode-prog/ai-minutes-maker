const form = document.getElementById("uploadForm");
const audioFile = document.getElementById("audioFile");
const fileNameLabel = document.getElementById("fileName");
const submitBtn = document.getElementById("submitBtn");
const errorMsg = document.getElementById("errorMsg");
const loading = document.getElementById("loading");
const resultSection = document.getElementById("resultSection");
const dropZone = document.getElementById("dropZone");

// ファイル選択時のファイル名表示
audioFile.addEventListener("change", () => {
  const file = audioFile.files[0];
  fileNameLabel.textContent = file ? file.name : "ファイル未選択";
});

// ドラッグ＆ドロップ
dropZone.addEventListener("dragover", (e) => {
  e.preventDefault();
  dropZone.classList.add("drag-over");
});

dropZone.addEventListener("dragleave", () => {
  dropZone.classList.remove("drag-over");
});

dropZone.addEventListener("drop", (e) => {
  e.preventDefault();
  dropZone.classList.remove("drag-over");

  const files = e.dataTransfer.files;
  if (files.length > 0) {
    const dt = new DataTransfer();
    dt.items.add(files[0]);
    audioFile.files = dt.files;
    fileNameLabel.textContent = files[0].name;
  }
});

// フォーム送信
form.addEventListener("submit", async (e) => {
  e.preventDefault();

  hideError();

  const file = audioFile.files[0];
  if (!file) {
    showError("ファイルが選択されていません。");
    return;
  }

  const allowed = ["audio/mpeg", "audio/wav", "audio/x-m4a", "audio/mp4", "audio/m4a"];
  const ext = file.name.split(".").pop().toLowerCase();
  const allowedExt = ["mp3", "wav", "m4a"];
  if (!allowedExt.includes(ext)) {
    showError("対応していないファイル形式です。mp3 / wav / m4a をアップロードしてください。");
    return;
  }

  const formData = new FormData();
  formData.append("audio", file);

  setLoading(true);

  try {
    const res = await fetch("/upload", {
      method: "POST",
      body: formData,
    });

    const data = await res.json();

    if (!res.ok || data.error) {
      showError(data.error || "予期しないエラーが発生しました。");
      return;
    }

    document.getElementById("transcription").textContent = data.transcription;
    document.getElementById("minutes").textContent = data.minutes;
    resultSection.hidden = false;
    resultSection.scrollIntoView({ behavior: "smooth", block: "start" });
  } catch (err) {
    showError("通信エラーが発生しました。ネットワーク接続を確認してください。");
  } finally {
    setLoading(false);
  }
});

function setLoading(isLoading) {
  loading.hidden = !isLoading;
  submitBtn.disabled = isLoading;
  submitBtn.textContent = isLoading ? "生成中..." : "議事録を生成する";
  if (isLoading) {
    resultSection.hidden = true;
  }
}

function showError(message) {
  errorMsg.textContent = message;
  errorMsg.hidden = false;
}

function hideError() {
  errorMsg.textContent = "";
  errorMsg.hidden = true;
}

async function copyMinutes() {
  const text = document.getElementById("minutes").textContent;
  try {
    await navigator.clipboard.writeText(text);
    const feedback = document.getElementById("copyFeedback");
    feedback.hidden = false;
    setTimeout(() => {
      feedback.hidden = true;
    }, 2500);
  } catch {
    // フォールバック（古いブラウザ向け）
    const textarea = document.createElement("textarea");
    textarea.value = text;
    document.body.appendChild(textarea);
    textarea.select();
    document.execCommand("copy");
    document.body.removeChild(textarea);
    const feedback = document.getElementById("copyFeedback");
    feedback.hidden = false;
    setTimeout(() => { feedback.hidden = true; }, 2500);
  }
}

function resetForm() {
  form.reset();
  fileNameLabel.textContent = "ファイル未選択";
  resultSection.hidden = true;
  hideError();
  window.scrollTo({ top: 0, behavior: "smooth" });
}
