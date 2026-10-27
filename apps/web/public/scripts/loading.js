(() => {
  const root = document.querySelector('#root');
  if (!root || root.innerHTML !== '') return;
  root.innerHTML = `
    <style>
      html,body,#root{height:100%;margin:0}
      body{background:#f3f6f4;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","Noto Sans SC",sans-serif}
      .initial-loader{height:100%;display:flex;flex-direction:column;align-items:center;justify-content:center;color:#334155}
      .initial-loader-mark{width:48px;height:48px;display:grid;place-items:center;margin-bottom:20px;background:#102c30;border-radius:15px;box-shadow:0 12px 30px rgba(15,39,44,.12)}
      .initial-loader-mark:before{content:"";width:20px;height:20px;border:2px solid #5eead4;border-right-color:transparent;border-radius:50%;animation:initial-spin 1s linear infinite}
      .initial-loader-title{font-size:15px;font-weight:600;letter-spacing:.04em}
      .initial-loader-copy{margin-top:8px;color:#8a9aa5;font-size:12px}
      @keyframes initial-spin{to{transform:rotate(360deg)}}
      @media(prefers-reduced-motion:reduce){.initial-loader-mark:before{animation:none;border-right-color:#5eead4}}
    </style>
    <div class="initial-loader" role="status" aria-live="polite">
      <div class="initial-loader-mark"></div>
      <div class="initial-loader-title">金蝶数据同步</div>
      <div class="initial-loader-copy">正在准备数据运营工作台</div>
    </div>`;
})();
