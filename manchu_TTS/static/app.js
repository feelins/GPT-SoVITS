const sourceText = document.getElementById('sourceText');
const latinText = document.getElementById('latinText');
const cmuText = document.getElementById('cmuText');
const btnConvert = document.getElementById('btnConvert');
const btnSynthesize = document.getElementById('btnSynthesize');
const resultArea = document.getElementById('resultArea');
const audioUrl = document.getElementById('audioUrl');
const audioPlayer = document.getElementById('audioPlayer');
const specImage = document.getElementById('specImage');
const logBox = document.getElementById('logBox');

function log(msg) {
  const now = new Date().toLocaleTimeString();
  logBox.textContent += `[${now}] ${msg}\n`;
}

async function postJson(url, payload) {
  const resp = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  const data = await resp.json();
  if (!resp.ok) {
    const detail = data?.detail || data?.message || '请求失败';
    throw new Error(typeof detail === 'string' ? detail : JSON.stringify(detail));
  }
  return data;
}

btnConvert.addEventListener('click', async () => {
  const text = sourceText.value.trim();
  if (!text) {
    log('请输入文本后再转化。');
    return;
  }
  try {
    log('正在转化文本（原文 -> 拉丁规范化 -> CMUdict）...');
    const data = await postJson('/api/convert', { text });
    latinText.value = data.latin_text || '';
    cmuText.value = data.cmudict_text || '';
    log('转化完成。');
  } catch (err) {
    log(`转化失败: ${err.message}`);
  }
});

btnSynthesize.addEventListener('click', async () => {
  const text = sourceText.value.trim();
  if (!text) {
    log('请输入文本后再合成。');
    return;
  }
  try {
    log('正在合成语音，请稍候（首次加载模型会更慢）...');
    const data = await postJson('/api/synthesize', { text });
    latinText.value = data.latin_text || '';
    cmuText.value = data.cmudict_text || '';

    audioUrl.href = data.audio_url;
    audioUrl.textContent = location.origin + data.audio_url;
    audioPlayer.src = data.audio_url;
    specImage.src = data.spectrogram_url;

    resultArea.classList.remove('hidden');
    log('合成完成，可在线播放与查看频谱。');
  } catch (err) {
    log(`合成失败: ${err.message}`);
  }
});
