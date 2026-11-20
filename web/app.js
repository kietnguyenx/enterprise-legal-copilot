// SecureDoc AI — app.js
// Kết nối trực tiếp Frontend SecureDoc AI (Trang chủ + Live Audit Canvas) với Backend FastAPI

(function() {
  'use strict';

  // Tự động đính kèm Supabase JWT Bearer Token / thông tin User cho mọi API nội bộ
  const _nativeFetch = window.fetch.bind(window);
  function getAuthHeaders(extra = {}) {
    const headers = Object.assign({}, extra);
    const token = localStorage.getItem('securedoc_access_token');
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    } else {
      try {
        const rawUser = localStorage.getItem('securedoc_user');
        if (rawUser) {
          const u = JSON.parse(rawUser);
          if (u && u.email) headers['X-User-Email'] = encodeURIComponent(u.email);
          if (u && u.name) headers['X-User-Name'] = encodeURIComponent(u.name);
        }
      } catch (e) {}
    }
    return headers;
  }

  function fetch(url, options = {}) {
    if (typeof url === 'string' && url.startsWith('/api/')) {
      const nextOpts = Object.assign({}, options);
      nextOpts.headers = getAuthHeaders(options.headers || {});
      return _nativeFetch(url, nextOpts);
    }
    return _nativeFetch(url, options);
  }

  let currentSessionId = null;
  let selectedModel = 'gemini-3.5-flash';
  let piiGuardEnabled = true;
  let sessionsCache = [];

  // ================= 1. DOM REFERENCES =================
  const globalFileInput = document.getElementById('global-file-input');

  // Home elements
  const homeTextarea = document.getElementById('q');
  const homeSendBtn = document.getElementById('home-send-btn');
  const homeAttachBtn = document.getElementById('home-attach-btn');
  const homePiiBtn = document.getElementById('home-pii-btn');
  const homePiiLabel = document.getElementById('home-pii-label');
  const homeModelBtn = document.getElementById('home-model-btn');
  const homeModelLabel = document.getElementById('home-model-label');
  const homeModelMenu = document.getElementById('home-model-menu');
  const homePinnedList = document.getElementById('home-pinned-list');
  const auditPinnedList = document.getElementById('audit-pinned-list');
  const homeHistoryList = document.getElementById('home-history-list');
  const histCountBadge = document.getElementById('hist-count-badge');
  const btnClearHistory = document.getElementById('btn-clear-history');
  const btnHomeNew = document.getElementById('btn-home-new');
  const btnCloseHomeSide = document.getElementById('btn-close-home-side');

  // Audit elements
  const auditDocName = document.getElementById('audit-doc-name');
  const auditModelBtn = document.getElementById('audit-model-btn');
  const auditModelLabel = document.getElementById('audit-model-label');
  const auditModelMenu = document.getElementById('audit-model-menu');
  const btnAuditNew = document.getElementById('btn-audit-new');
  const btnToggleAuditSide = document.getElementById('btn-toggle-audit-side');
  const auditFirstUserMsg = document.getElementById('audit-first-user-msg');
  const auditPiiCard = document.getElementById('audit-pii-card');
  const auditPiiSummary = document.getElementById('audit-pii-summary');
  const auditPiiTokens = document.getElementById('audit-pii-tokens');
  const auditExecSummary = document.getElementById('audit-exec-summary');
  const countHigh = document.getElementById('count-high');
  const countMed = document.getElementById('count-med');
  const countLow = document.getElementById('count-low');
  const auditRecText = document.getElementById('audit-rec-text');
  const auditCursor = document.getElementById('audit-cursor');
  const auditExtraMessages = document.getElementById('audit-extra-messages');
  const auditInput = document.getElementById('audit-input');
  const auditSendBtn = document.getElementById('audit-send-btn');
  const auditAttachBtn = document.getElementById('audit-attach-btn');

  // Live Audit Canvas elements
  const btnExportDocx = document.getElementById('btn-export-docx');
  const auditGaugeCircle = document.getElementById('audit-gauge-circle');
  const auditGaugeScore = document.getElementById('audit-gauge-score');
  const auditRiskDesc = document.getElementById('audit-risk-desc');
  const auditRiskSub = document.getElementById('audit-risk-sub');
  const auditClauseRows = document.getElementById('audit-clause-rows');
  const auditQuoteTitle = document.getElementById('audit-quote-title');
  const auditQuoteBody = document.getElementById('audit-quote-body');
  const auditRedlineBody = document.getElementById('audit-redline-body');

  // Scenario Matrix elements
  const scenarioAggressiveText = document.getElementById('scenario-aggressive-text');
  const scenarioBalancedText = document.getElementById('scenario-balanced-text');
  const scenarioConservativeText = document.getElementById('scenario-conservative-text');

  // NotebookLM Studio elements
  const studioBriefingList = document.getElementById('studio-briefing-list');
  const studioTimelineList = document.getElementById('studio-timeline-list');
  const studioMissingList = document.getElementById('studio-missing-list');
  const studioFaqList = document.getElementById('studio-faq-list');

  // ================= 2. MODEL SELECTION =================
  async function initModels() {
    try {
      const res = await fetch('/api/models');
      const models = await res.json();
      if (!Array.isArray(models) || !models.length) return;

      const renderMenu = (menuEl, labelEl) => {
        if (!menuEl) return;
        menuEl.innerHTML = models.map(m => `
          <div class="dropdown-item ${m.id === selectedModel ? 'active' : ''}" data-model="${m.id}">
            ✦ ${escapeHtml(m.label)}
          </div>
        `).join('');

        menuEl.querySelectorAll('.dropdown-item').forEach(el => {
          el.addEventListener('click', (e) => {
            e.stopPropagation();
            selectedModel = el.dataset.model;
            const chosen = models.find(m => m.id === selectedModel);
            const title = chosen ? chosen.label : selectedModel;
            if (homeModelLabel) homeModelLabel.textContent = title;
            if (auditModelLabel) auditModelLabel.textContent = title;

            document.querySelectorAll('.model-dropdown-menu .dropdown-item').forEach(it => {
              it.classList.toggle('active', it.dataset.model === selectedModel);
            });
            closeAllMenus();
          });
        });
      };

      renderMenu(homeModelMenu, homeModelLabel);
      renderMenu(auditModelMenu, auditModelLabel);

      const def = models[0];
      selectedModel = def.id;
      if (homeModelLabel) homeModelLabel.textContent = def.label;
      if (auditModelLabel) auditModelLabel.textContent = def.label;
    } catch (e) {
      console.warn('Cannot load models:', e);
    }
  }

  function toggleDropdown(btn, menu) {
    if (!btn || !menu) return;
    btn.addEventListener('click', (e) => {
      e.stopPropagation();
      const isShow = menu.classList.contains('show');
      closeAllMenus();
      if (!isShow) menu.classList.add('show');
    });
  }

  function closeAllMenus() {
    if (homeModelMenu) homeModelMenu.classList.remove('show');
    if (auditModelMenu) auditModelMenu.classList.remove('show');
  }

  toggleDropdown(homeModelBtn, homeModelMenu);
  toggleDropdown(auditModelBtn, auditModelMenu);
  document.addEventListener('click', closeAllMenus);

  // ================= 3. SESSIONS & HISTORY =================
  async function loadSessions() {
    try {
      const res = await fetch('/api/sessions');
      if (!res.ok) return;
      sessionsCache = await res.json();
      renderSidebar();
    } catch (e) {
      console.warn('Cannot load sessions:', e);
    }
  }

  function renderSidebar() {
    // 1. Pinned Projects (sessions with files) - render to both home and audit sidebars
    const populatePinned = (container) => {
      if (!container) return;
      const docSessions = sessionsCache.filter(s => s.file_name);
      if (docSessions.length) {
        container.innerHTML = docSessions.slice(0, 5).map(s => `
          <button class="nav ${s.id === currentSessionId ? 'on' : ''}" data-id="${s.id}" title="${escapeHtml(s.file_name)}" style="width:100%;text-align:left;cursor:pointer;">
            <svg class="i" viewBox="0 0 24 24" aria-hidden="true"><path d="M7 3h7l4 4v14H7zM14 3v4h4"/></svg>
            <span style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">${escapeHtml(s.file_name)}</span>
          </button>
        `).join('');
      } else {
        container.innerHTML = `
          <button class="nav" style="width:100%;text-align:left;"><svg class="i" viewBox="0 0 24 24" aria-hidden="true"><path d="M7 3h7l4 4v14H7zM14 3v4h4"/></svg>HĐ thuê văn phòng Q4</button>
          <button class="nav" style="width:100%;text-align:left;"><svg class="i" viewBox="0 0 24 24" aria-hidden="true"><path d="M7 3h7l4 4v14H7zM14 3v4h4"/></svg>HĐ cung cấp phần mềm</button>
          <button class="nav" style="width:100%;text-align:left;"><svg class="i" viewBox="0 0 24 24" aria-hidden="true"><path d="M7 3h7l4 4v14H7zM14 3v4h4"/></svg>NDA đối tác Nhật Bản</button>
        `;
      }

      container.querySelectorAll('.nav[data-id]').forEach(btn => {
        btn.addEventListener('click', () => openSession(btn.dataset.id));
      });
    };

    populatePinned(homePinnedList);
    populatePinned(auditPinnedList);

    // 2. History List (with checkboxes)
    if (homeHistoryList) {
      if (histCountBadge) {
        histCountBadge.textContent = `${sessionsCache.length}/50`;
      }

      if (sessionsCache.length) {
        homeHistoryList.innerHTML = sessionsCache.slice(0, 8).map(s => {
          const title = s.title || s.file_name || 'Cuộc trò chuyện';
          let sub = 'Audit Risk · Thẩm định rủi ro';
          if (s.audit && s.audit.risk_counts) {
            sub = `Audit Risk · ${s.audit.risk_counts.high || 0} rủi ro cao, điểm ${s.audit.risk_score || 0}/100`;
          } else if (s.messages && s.messages.length > 1) {
            sub = s.messages[s.messages.length - 1].content.slice(0, 40) + '…';
          }

          return `
            <label class="hi ${s.id === currentSessionId ? 's52' : ''}" data-id="${s.id}">
              <input type="checkbox" class="hist-checkbox" data-id="${s.id}" aria-label="Chọn">
              <div class="hist-text-wrap" style="flex:1;min-width:0;cursor:pointer;">
                <b style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap;display:block;">${escapeHtml(title)}</b>
                <span style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap;display:block;">${escapeHtml(sub)}</span>
              </div>
            </label>
          `;
        }).join('');

        homeHistoryList.querySelectorAll('.hist-text-wrap').forEach(wrap => {
          wrap.addEventListener('click', (e) => {
            const sid = wrap.closest('.hi').dataset.id;
            openSession(sid);
          });
        });
      }
    }
  }

  async function openSession(sid) {
    try {
      const res = await fetch(`/api/sessions/${sid}`);
      if (!res.ok) return;
      const s = await res.json();
      currentSessionId = s.id;
      applySessionToViews(s);
      renderSidebar();
      window.location.hash = 'audit';
    } catch (e) {
      console.warn('Cannot open session:', e);
    }
  }

  function applySessionToViews(s) {
    const docTitle = s.file_name || s.title || 'HD_ThueVanPhong_Q4.docx';
    const audit = s.audit || {};
    const score = audit.risk_score || 72;
    const counts = audit.risk_counts || { high: 3, medium: 5, low: 8 };

    // Document Name
    if (auditDocName) auditDocName.textContent = docTitle;

    // First user message
    const firstUser = (s.messages || []).find(m => m.role === 'user');
    if (auditFirstUserMsg) {
      auditFirstUserMsg.textContent = firstUser ? firstUser.content : 'Thẩm định rủi ro hợp đồng này giúp tôi (Audit Risk).';
    }

    // PII Card
    if (auditPiiCard) {
      if (s.pii && Object.keys(s.pii).length > 0) {
        const totalPii = Object.values(s.pii).reduce((a, b) => a + b, 0);
        if (auditPiiSummary) auditPiiSummary.textContent = `PII Guard đã ẩn ${totalPii} thông tin nhạy cảm`;
        const pills = [];
        if (s.pii.phone) pills.push(`<span class="pii">[PHONE_${s.pii.phone}]</span>`);
        if (s.pii.id) pills.push(`<span class="pii">[ID_${s.pii.id}]</span>`);
        if (s.pii.email) pills.push(`<span class="pii">[EMAIL_${s.pii.email}]</span>`);
        if (s.pii.bank) pills.push(`<span class="pii">[BANK_${s.pii.bank}]</span>`);
        if (auditPiiTokens) auditPiiTokens.innerHTML = pills.join(' ') + (totalPii > 4 ? ` <span class="s72">+${totalPii - 4}</span>` : '');
      } else {
        if (auditPiiSummary) auditPiiSummary.textContent = 'PII Guard đang bật (Zero-Retention)';
        if (auditPiiTokens) auditPiiTokens.innerHTML = '<span class="pii">[ĐÃ BẢO VỆ AN TOÀN]</span>';
      }
    }

    // Executive summary & counts
    if (auditExecSummary) {
      auditExecSummary.innerHTML = audit.executive_summary || (audit.summary ? audit.summary.join('<br>') : 'Hợp đồng thuê văn phòng 24 tháng. Phần lớn điều khoản tiêu chuẩn, nhưng có 2 điều khoản bất lợi nghiêm trọng cho Bên B.');
    }
    if (countHigh) countHigh.textContent = counts.high ?? 0;
    if (countMed) countMed.textContent = counts.medium ?? 0;
    if (countLow) countLow.textContent = counts.low ?? 0;
    if (auditRecText) {
      auditRecText.innerHTML = audit.recommendation || (audit.high_risk ? audit.high_risk.desc : 'Đề xuất rút ngắn mức phạt và bổ sung quyền khắc phục trong 30 ngày.');
    }

    // Live Audit Canvas: Gauge circle
    const dashLength = Math.min(264, Math.max(0, Math.round((score / 100) * 264)));
    let riskDescText = 'Rủi ro pháp lý cao';
    let riskColor = '#C2410C';
    if (score >= 70) {
      riskDescText = 'Rủi ro pháp lý cao';
      riskColor = '#C2410C';
    } else if (score >= 45) {
      riskDescText = 'Rủi ro pháp lý trung bình';
      riskColor = '#D97706';
    } else {
      riskDescText = 'Rủi ro pháp lý thấp (An toàn)';
      riskColor = '#0B5A4E';
    }

    if (auditGaugeScore) auditGaugeScore.textContent = score;
    if (auditGaugeCircle) {
      auditGaugeCircle.setAttribute('stroke-dasharray', `${dashLength} 264`);
      auditGaugeCircle.setAttribute('stroke', riskColor);
    }
    if (auditRiskDesc) auditRiskDesc.textContent = riskDescText;
    if (auditRiskSub) {
      const reviewed = audit.clauses_reviewed || (audit.clauses ? audit.clauses.length : 16);
      auditRiskSub.textContent = `${reviewed} điều khoản được rà soát · cần sửa ${counts.high || 1} điều khoản trước khi ký`;
    }

    // Clauses table
    const clauses = audit.clauses || [];
    if (auditClauseRows && clauses.length) {
      auditClauseRows.innerHTML = clauses.map(c => {
        let tagCls = 'lo';
        const st = (c.status || '').toLowerCase();
        if (st.includes('cao') || st.includes('high')) tagCls = 'hi';
        else if (st.includes('trung') || st.includes('med')) tagCls = 'md';

        const actionText = c.action || (tagCls === 'hi' ? 'Đề xuất sửa' : (tagCls === 'md' ? 'Cần xem xét' : 'Chấp nhận'));
        const actionCls = tagCls === 'hi' ? 's96' : 's72';
        return `
          <div class="row">
            <b>${escapeHtml(c.ref || '')}</b>
            <span>${escapeHtml(c.topic || '')}</span>
            <span><span class="tag ${tagCls}">${escapeHtml(c.status || '')}</span></span>
            <span class="${actionCls}">${escapeHtml(actionText)}</span>
          </div>
        `;
      }).join('');
    }

    // Quote
    if (auditQuoteTitle) auditQuoteTitle.textContent = `Quote · ${audit.quote_ref || 'Điều 5.2'}`;
    if (auditQuoteBody) {
      auditQuoteBody.innerHTML = audit.source_quote || '“Bên B vi phạm bất kỳ nghĩa vụ nào sẽ chịu phạt <b>30%</b> tổng giá trị hợp đồng, không phụ thuộc mức thiệt hại thực tế.”';
    }

    // Redline Diff
    const redline = audit.redline_diff || {};
    if (auditRedlineBody) {
      if (redline.original && redline.revised) {
        auditRedlineBody.innerHTML = `Bên B vi phạm nghĩa vụ sẽ chịu phạt <del class="s99">${escapeHtml(redline.original)}</del> <ins class="s100">${escapeHtml(redline.revised)}</ins>.`;
      }
    }

    // Ma trận 3 Kịch bản Đàm phán (Scenario Matrix)
    const scenarios = audit.negotiation_scenarios || {};
    if (scenarioAggressiveText) {
      scenarioAggressiveText.textContent = scenarios.aggressive?.strategy || 'Đòi xóa bỏ hoàn toàn điều khoản phạt vi phạm 30% và siết chặt chế tài đối tác theo quy định pháp luật thương mại.';
    }
    if (scenarioBalancedText) {
      scenarioBalancedText.textContent = scenarios.balanced?.strategy || 'Đưa về trần 8% theo Điều 301 Luật Thương mại và bổ sung thời hạn ân hạn 30 ngày để khắc phục vi phạm.';
    }
    if (scenarioConservativeText) {
      scenarioConservativeText.textContent = scenarios.conservative?.strategy || 'Giới hạn tổng mức bồi thường theo thiệt hại thực tế tối đa và yêu cầu mua bảo hiểm trách nhiệm pháp lý.';
    }

    // NotebookLM Studio Suite
    const studio = audit.notebooklm_studio || {};
    if (studioBriefingList) {
      const briefingItems = (studio.executive_briefing && studio.executive_briefing.length) ? studio.executive_briefing : [
        `Đối tượng giao dịch: ${docTitle}`,
        `Điểm rủi ro cao nhất: Điều khoản phạt vi phạm 30% vượt quá trần 8% của Luật Thương mại.`,
        `Quyền đơn phương: Cần bổ sung nghĩa vụ gửi thông báo trước tối thiểu 15-30 ngày.`,
        `Khuyến nghị ký kết: Đàm phán sửa đổi Điều 3 và 5 theo kịch bản Win-Win trước khi ký kết.`
      ];
      studioBriefingList.innerHTML = briefingItems.map(item => `<li>${escapeHtml(item)}</li>`).join('');
    }

    if (studioTimelineList) {
      const milestones = (studio.timeline_milestones && studio.timeline_milestones.length) ? studio.timeline_milestones : [
        { event: 'Ký kết hợp đồng & hoàn tất thanh toán đợt 1', deadline: 'Ngày T+0' },
        { event: 'Bàn giao mặt bằng & hồ sơ pháp lý kèm theo', deadline: 'Trong 05 ngày làm việc' },
        { event: 'Thời hạn ân hạn khắc phục vi phạm nghĩa vụ', deadline: 'Tối thiểu 15 - 30 ngày' }
      ];
      studioTimelineList.innerHTML = milestones.map(m => `
        <div class="timeline-item">
          <div class="timeline-header">
            <span class="timeline-event">${escapeHtml(m.event || '')}</span>
            <span class="timeline-badge">${escapeHtml(m.deadline || '')}</span>
          </div>
        </div>
      `).join('');
    }

    if (studioMissingList) {
      const missing = (studio.missing_clauses && studio.missing_clauses.length) ? studio.missing_clauses : [
        'Thiếu điều khoản Sự kiện Bất khả kháng (Force Majeure) theo chuẩn Điều 156 Bộ luật Dân sự 2015.',
        'Chưa quy định mức trần giới hạn tổng trách nhiệm bồi thường thiệt hại (Liability Cap).',
        'Thiếu quy trình bắt buộc gửi thông báo vi phạm bằng văn bản trước khi áp dụng chế tài.'
      ];
      studioMissingList.innerHTML = missing.map(item => `
        <div class="missing-item">
          <span class="missing-icon">⚠️</span>
          <span>${escapeHtml(item)}</span>
        </div>
      `).join('');
    }

    if (studioFaqList) {
      const faqs = (studio.suggested_faq && studio.suggested_faq.length) ? studio.suggested_faq : [
        {
          question: 'Mức phạt vi phạm 30% trong hợp đồng có hiệu lực không?',
          answer: 'Theo Điều 301 Luật Thương mại 2005, mức phạt vi phạm do các bên thoả thuận nhưng không quá 8% giá trị phần nghĩa vụ bị vi phạm. Mức phạt 30% vi phạm điều cấm của luật và không có hiệu lực thi hành đối với phần vượt quá.'
        },
        {
          question: 'Bên thuê có quyền đơn phương chấm dứt hợp đồng khi nào?',
          answer: 'Chỉ được đơn phương chấm dứt khi bên cho thuê vi phạm nghiêm trọng nghĩa vụ hợp đồng và đã được thông báo bằng văn bản nhưng không khắc phục trong thời hạn thỏa thuận.'
        }
      ];
      studioFaqList.innerHTML = faqs.map(f => `
        <div class="faq-item">
          <div class="faq-q">${escapeHtml(f.question || '')}</div>
          <div class="faq-a">${escapeHtml(f.answer || '')}</div>
        </div>
      `).join('');
    }

    // Extra messages with HITL actions
    const extraMsgs = (s.messages || []).slice(1);
    if (auditExtraMessages) {
      if (extraMsgs.length) {
        auditExtraMessages.innerHTML = extraMsgs.map((m, idx) => {
          if (m.role === 'user') {
            return `<div class="s69" style="margin-top:10px">${escapeHtml(m.content || '')}</div>`;
          } else {
            return `
              <div class="card s73" style="margin-top:10px" data-msg-idx="${idx + 1}">
                <p class="h">SecureDoc AI</p>
                <div class="ai-msg-body" style="font-size:14px;line-height:1.6;color:#0F2147;">${formatMarkdown(m.content || '')}</div>
                ${renderHitlBar(idx + 1)}
              </div>
            `;
          }
        }).join('');
        attachHitlEvents(auditExtraMessages);
      } else {
        auditExtraMessages.innerHTML = '';
      }
    }
  }

  // ================= 4. FILE UPLOAD =================
  document.querySelectorAll('.btn-attach-trigger').forEach(btn => {
    btn.addEventListener('click', (e) => {
      e.preventDefault();
      if (globalFileInput) globalFileInput.click();
    });
  });

  if (globalFileInput) {
    globalFileInput.addEventListener('change', () => {
      if (globalFileInput.files && globalFileInput.files[0]) {
        uploadFile(globalFileInput.files[0]);
      }
    });
  }

  // Drag & drop on Home textarea
  if (homeTextarea) {
    ['dragenter', 'dragover'].forEach(name => {
      homeTextarea.addEventListener(name, (e) => {
        e.preventDefault();
        homeTextarea.style.background = 'rgba(47,107,255,0.06)';
      });
    });
    ['dragleave', 'drop'].forEach(name => {
      homeTextarea.addEventListener(name, (e) => {
        e.preventDefault();
        homeTextarea.style.background = 'transparent';
      });
    });
    homeTextarea.addEventListener('drop', (e) => {
      if (e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files[0]) {
        uploadFile(e.dataTransfer.files[0]);
      }
    });
  }

  async function uploadFile(file) {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('model', selectedModel);
    formData.append('pii_guard', piiGuardEnabled ? 'true' : 'false');

    const origPlaceholder = homeTextarea ? homeTextarea.placeholder : '';
    if (homeTextarea) homeTextarea.placeholder = `⏳ Đang tải lên và thẩm định ${file.name}...`;

    try {
      const res = await fetch('/api/upload', {
        method: 'POST',
        body: formData,
      });
      if (!res.ok) {
        if (res.status === 401) {
          const modal = document.getElementById('guest-limit-modal');
          if (modal) {
            modal.style.display = 'flex';
            return;
          }
        }
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || 'Lỗi khi tải file lên');
      }
      const data = await res.json();
      currentSessionId = data.id;
      await loadSessions();
      applySessionToViews(data);
      window.location.hash = 'audit';
    } catch (e) {
      alert(`Không thể thẩm định tài liệu: ${e.message}`);
    } finally {
      if (homeTextarea) homeTextarea.placeholder = origPlaceholder;
    }
  }

  // ================= 5. SEND MESSAGE HANDLERS =================
  // A. Home Send
  if (homeSendBtn && homeTextarea) {
    homeSendBtn.addEventListener('click', (e) => {
      e.preventDefault();
      sendFromHome();
    });
    homeTextarea.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendFromHome();
      }
    });
  }

  async function sendFromHome() {
    const text = (homeTextarea.value || '').trim();
    if (!text) return;
    homeTextarea.value = '';

    window.location.hash = 'audit';
    if (auditFirstUserMsg) auditFirstUserMsg.textContent = text;
    if (auditDocName) auditDocName.textContent = 'Cuộc trò chuyện mới';
    if (auditPiiCard) auditPiiCard.style.display = 'flex';
    if (auditPiiSummary) auditPiiSummary.textContent = 'PII Guard đang bật';
    if (auditPiiTokens) auditPiiTokens.innerHTML = '<span class="pii">[ĐÃ BẢO VỆ]</span>';
    if (auditExecSummary) auditExecSummary.textContent = '';
    if (auditRecText) auditRecText.textContent = '';
    if (auditCursor) auditCursor.style.display = 'inline-block';
    if (auditExtraMessages) auditExtraMessages.innerHTML = '';

    await streamAiChat(null, text, (chunk) => {
      if (auditExecSummary) auditExecSummary.textContent += chunk;
    }, () => {
      if (auditCursor) auditCursor.style.display = 'none';
      loadSessions();
    });
  }

  // B. Audit Send
  if (auditSendBtn && auditInput) {
    auditSendBtn.addEventListener('click', (e) => {
      e.preventDefault();
      sendFromAudit();
    });
    auditInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') {
        e.preventDefault();
        sendFromAudit();
      }
    });
  }

  async function sendFromAudit() {
    const text = (auditInput.value || '').trim();
    if (!text) return;
    auditInput.value = '';

    if (auditExtraMessages) {
      const userBubble = document.createElement('div');
      userBubble.className = 's69';
      userBubble.style.marginTop = '10px';
      userBubble.textContent = text;
      auditExtraMessages.appendChild(userBubble);

      const aiCard = document.createElement('div');
      aiCard.className = 'card s73';
      aiCard.style.marginTop = '10px';
      aiCard.innerHTML = `<p class="h">SecureDoc AI</p><div class="ai-stream-content" style="font-size:14px;line-height:1.6;color:#0F2147;"></div><span class="cursor-blink"></span>`;
      auditExtraMessages.appendChild(aiCard);

      const streamEl = aiCard.querySelector('.ai-stream-content');
      const cursorEl = aiCard.querySelector('.cursor-blink');

      await streamAiChat(currentSessionId, text, (chunk) => {
        streamEl.textContent += chunk;
      }, () => {
        if (cursorEl) cursorEl.remove();
        streamEl.innerHTML = formatMarkdown(streamEl.textContent);
        
        // Append HITL action bar
        const totalCards = auditExtraMessages.querySelectorAll('.card.s73').length;
        const hitlContainer = document.createElement('div');
        hitlContainer.innerHTML = renderHitlBar(totalCards);
        while (hitlContainer.firstChild) {
          aiCard.appendChild(hitlContainer.firstChild);
        }
        attachHitlEvents(aiCard);

        loadSessions();
      });
    }
  }

  // ================= 6. STREAM AI CHAT =================
  async function streamAiChat(sessionId, message, onChunk, onDone) {
    try {
      const res = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: sessionId,
          message: message,
          model: selectedModel,
          pii_guard: piiGuardEnabled,
        }),
      });

      const newSid = res.headers.get('X-Session-Id');
      if (newSid) currentSessionId = newSid;

      if (!res.ok) {
        if (res.status === 401) {
          const modal = document.getElementById('guest-limit-modal');
          if (modal) modal.style.display = 'flex';
          if (onChunk) onChunk('🔒 Bạn đã dùng hết 3 lượt trải nghiệm miễn phí. Vui lòng đăng nhập để tiếp tục sử dụng không giới hạn.');
          if (onDone) onDone();
          return;
        }
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || 'Lỗi từ máy chủ AI');
      }

      const reader = res.body.getReader();
      const decoder = new TextDecoder('utf-8');
      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        const chunk = decoder.decode(value, { stream: true });
        if (chunk) onChunk(chunk);
      }
    } catch (e) {
      onChunk(`\n[Lỗi kết nối: ${e.message}]`);
    } finally {
      if (onDone) onDone();
    }
  }

  // ================= 7. CHIPS & BUTTONS =================
  // Home Cards
  document.querySelectorAll('.quick-card').forEach(card => {
    card.addEventListener('click', () => {
      const prompt = card.dataset.prompt;
      if (homeTextarea && prompt) {
        homeTextarea.value = prompt;
        homeTextarea.focus();
      }
    });
  });

  // Audit Chips
  document.querySelectorAll('.quick-chip').forEach(chip => {
    chip.addEventListener('click', () => {
      const prompt = chip.dataset.prompt;
      if (auditInput && prompt) {
        auditInput.value = prompt;
        sendFromAudit();
      }
    });
  });

  // PII Guard Toggle
  if (homePiiBtn) {
    homePiiBtn.addEventListener('click', () => {
      piiGuardEnabled = !piiGuardEnabled;
      if (piiGuardEnabled) {
        homePiiBtn.classList.remove('pii-off');
        if (homePiiLabel) homePiiLabel.textContent = 'PII Guard: On';
        homePiiBtn.style.background = '#D9F2EC';
        homePiiBtn.style.color = '#0B5A4E';
      } else {
        homePiiBtn.classList.add('pii-off');
        if (homePiiLabel) homePiiLabel.textContent = 'PII Guard: Off';
        homePiiBtn.style.background = '#FDE4E1';
        homePiiBtn.style.color = '#9A1B10';
      }
    });
  }

  // Export .docx (hỗ trợ tùy chọn giải mã PII gốc từ PII Vault)
  if (btnExportDocx) {
    btnExportDocx.addEventListener('click', () => {
      if (!currentSessionId) {
        alert('Chưa chọn phiên làm việc để xuất báo cáo.');
        return;
      }
      const restoreCheckbox = document.getElementById('toggle-restore-pii');
      const restorePii = restoreCheckbox && restoreCheckbox.checked ? 'true' : 'false';
      const token = localStorage.getItem('securedoc_access_token');
      const params = new URLSearchParams({ restore_original_pii: restorePii });
      if (token) params.set('token', token);
      window.location.href = `/api/sessions/${currentSessionId}/export?${params.toString()}`;
    });
  }

  // Clear History
  if (btnClearHistory) {
    btnClearHistory.addEventListener('click', async () => {
      const checkedBoxes = Array.from(document.querySelectorAll('.hist-checkbox:checked'));
      const idsToDelete = checkedBoxes.map(b => b.dataset.id);

      if (idsToDelete.length > 0) {
        if (!confirm(`Xóa ${idsToDelete.length} mục đã chọn trong lịch sử?`)) return;
        await fetch('/api/sessions/delete', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ ids: idsToDelete }),
        });
      } else {
        if (!confirm('Xóa toàn bộ lịch sử các phiên thẩm định?')) return;
        await fetch('/api/sessions/delete', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ ids: null }),
        });
      }
      await loadSessions();
    });
  }

  // New Conversation buttons & Brand Logo navigation to Home
  const navigateToHome = (e) => {
    if (e) e.preventDefault();
    if (homeTextarea) homeTextarea.value = '';
    if (typeof window.updateDynamicGreeting === 'function') {
      window.updateDynamicGreeting();
    }
    window.location.hash = 'home';
  };

  const auditBrandLogo = document.getElementById('audit-brand-logo');
  const homeBrandLogo = document.getElementById('home-brand-logo');
  if (auditBrandLogo) auditBrandLogo.addEventListener('click', navigateToHome);
  if (homeBrandLogo) homeBrandLogo.addEventListener('click', navigateToHome);

  if (btnHomeNew) {
    btnHomeNew.addEventListener('click', navigateToHome);
  }
  if (btnAuditNew) {
    btnAuditNew.addEventListener('click', navigateToHome);
  }

  // ================= 7. NOTEBOOKLM STUDIO & SCENARIO MATRIX =================
  // NotebookLM Studio Tab Switching
  document.querySelectorAll('.studio-tab').forEach(tabBtn => {
    tabBtn.addEventListener('click', () => {
      const tab = tabBtn.dataset.tab;
      document.querySelectorAll('.studio-tab').forEach(b => b.classList.toggle('active', b === tabBtn));
      document.querySelectorAll('.studio-view').forEach(view => {
        if (view.id === `studio-view-${tab}`) {
          view.style.display = 'block';
          view.classList.add('active');
        } else {
          view.style.display = 'none';
          view.classList.remove('active');
        }
      });
    });
  });

  // Scenario Matrix Apply Buttons
  document.querySelectorAll('.scenario-apply-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const sc = btn.dataset.scenario;
      let promptText = '';
      if (sc === 'aggressive') {
        const text = document.getElementById('scenario-aggressive-text')?.textContent || '';
        promptText = `Hãy giúp tôi soạn thảo lại các điều khoản trong hợp đồng này theo KỊCH BẢN CỨNG RẮN (Thế Áp Đảo): ${text}`;
      } else if (sc === 'balanced') {
        const text = document.getElementById('scenario-balanced-text')?.textContent || '';
        promptText = `Hãy giúp tôi soạn thảo lại các điều khoản trong hợp đồng này theo KỊCH BẢN CÂN BẰNG (Win - Win): ${text}`;
      } else if (sc === 'conservative') {
        const text = document.getElementById('scenario-conservative-text')?.textContent || '';
        promptText = `Hãy giúp tôi soạn thảo lại các điều khoản trong hợp đồng này theo KỊCH BẢN DỰ PHÒNG (Phòng Thủ): ${text}`;
      }
      if (auditInput && promptText) {
        auditInput.value = promptText;
        sendFromAudit();
      }
    });
  });

  // ================= 8. HITL (HUMAN-IN-THE-LOOP) FEEDBACK =================
  function renderHitlBar(msgIdx) {
    return `
      <div class="hitl-bar" data-msg-idx="${msgIdx}">
        <span class="hitl-prompt-text">Đánh giá tư vấn AI:</span>
        <button class="hitl-btn hitl-like" data-type="like" title="Câu trả lời chính xác, hữu ích">👍 Chuẩn xác</button>
        <button class="hitl-btn hitl-dislike" data-type="dislike" title="Cần cải thiện hoặc chỉnh sửa">👎 Chưa chuẩn</button>
        <button class="hitl-btn hitl-edit" title="Luật sư hiệu đính câu trả lời">✏️ Hiệu đính</button>
      </div>
      <div class="hitl-correction-box" style="display:none" data-msg-idx="${msgIdx}">
        <textarea class="hitl-correction-input" rows="2" placeholder="Nhập ý kiến chuyên gia hoặc nội dung chỉnh sửa chuẩn..."></textarea>
        <div class="hitl-correction-actions">
          <button class="hitl-correction-btn hitl-cancel-btn">Hủy</button>
          <button class="hitl-correction-btn hitl-submit-btn">Gửi hiệu đính</button>
        </div>
      </div>
    `;
  }

  function attachHitlEvents(container) {
    if (!container) return;
    
    // Thumbs Up / Like
    container.querySelectorAll('.hitl-like').forEach(btn => {
      btn.onclick = async (e) => {
        e.stopPropagation();
        const bar = btn.closest('.hitl-bar');
        const msgIdx = parseInt(bar?.dataset.msgIdx || '-1', 10);
        const card = btn.closest('.card');
        const originalText = card?.querySelector('.ai-msg-body, .ai-stream-content')?.textContent || '';

        try {
          await fetch('/api/feedback', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              session_id: currentSessionId || 'default',
              rating: 'like',
              message_index: msgIdx,
              original_text: originalText,
            }),
          });
          btn.classList.add('active-up');
          bar.querySelector('.hitl-dislike')?.classList.remove('active-down');
        } catch (err) {
          console.error('Feedback error:', err);
        }
      };
    });

    // Thumbs Down / Dislike
    container.querySelectorAll('.hitl-dislike').forEach(btn => {
      btn.onclick = async (e) => {
        e.stopPropagation();
        const bar = btn.closest('.hitl-bar');
        const msgIdx = parseInt(bar?.dataset.msgIdx || '-1', 10);
        const card = btn.closest('.card');
        const box = card?.querySelector(`.hitl-correction-box[data-msg-idx="${msgIdx}"]`);
        const originalText = card?.querySelector('.ai-msg-body, .ai-stream-content')?.textContent || '';

        try {
          await fetch('/api/feedback', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              session_id: currentSessionId || 'default',
              rating: 'dislike',
              message_index: msgIdx,
              original_text: originalText,
            }),
          });
          btn.classList.add('active-down');
          bar.querySelector('.hitl-like')?.classList.remove('active-up');
          if (box) {
            box.style.display = 'flex';
            box.querySelector('textarea')?.focus();
          }
        } catch (err) {
          console.error('Feedback error:', err);
        }
      };
    });

    // Edit Button
    container.querySelectorAll('.hitl-edit').forEach(btn => {
      btn.onclick = (e) => {
        e.stopPropagation();
        const bar = btn.closest('.hitl-bar');
        const msgIdx = parseInt(bar?.dataset.msgIdx || '-1', 10);
        const card = btn.closest('.card');
        const box = card?.querySelector(`.hitl-correction-box[data-msg-idx="${msgIdx}"]`);
        if (box) {
          const isHidden = box.style.display === 'none';
          box.style.display = isHidden ? 'flex' : 'none';
          if (isHidden) box.querySelector('textarea')?.focus();
        }
      };
    });

    // Cancel Button
    container.querySelectorAll('.hitl-cancel-btn').forEach(btn => {
      btn.onclick = (e) => {
        e.stopPropagation();
        const box = btn.closest('.hitl-correction-box');
        if (box) box.style.display = 'none';
      };
    });

    // Submit Correction Button
    container.querySelectorAll('.hitl-submit-btn').forEach(btn => {
      btn.onclick = async (e) => {
        e.stopPropagation();
        const box = btn.closest('.hitl-correction-box');
        const textarea = box?.querySelector('.hitl-correction-input');
        const userText = (textarea?.value || '').trim();
        if (!userText) {
          alert('Vui lòng nhập nội dung hiệu đính của bạn.');
          return;
        }

        const msgIdx = parseInt(box?.dataset.msgIdx || '-1', 10);
        const card = btn.closest('.card');
        const originalText = card?.querySelector('.ai-msg-body, .ai-stream-content')?.textContent || '';

        try {
          btn.disabled = true;
          btn.textContent = 'Đang lưu...';
          await fetch('/api/feedback', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              session_id: currentSessionId || 'default',
              rating: 'dislike',
              message_index: msgIdx,
              user_correction: userText,
              original_text: originalText,
            }),
          });
          btn.textContent = '✓ Đã lưu';
          setTimeout(() => {
            if (box) box.style.display = 'none';
            btn.disabled = false;
            btn.textContent = 'Gửi hiệu đính';
            const editBtn = card?.querySelector('.hitl-edit');
            if (editBtn) editBtn.textContent = '✓ Đã hiệu đính';
          }, 800);
        } catch (err) {
          alert('Không thể lưu hiệu đính: ' + err.message);
          btn.disabled = false;
          btn.textContent = 'Gửi hiệu đính';
        }
      };
    });
  }

  // ================= 9. TWO-MODE DYNAMIC SIDEBARS =================
  const auditSidebar = document.getElementById('audit-sidebar');
  const homeSidebar = document.getElementById('home-sidebar');

  // Audit Sidebar: Expand to Full Wide / Collapse to Narrow
  const btnCollapseAuditSide = document.getElementById('btn-collapse-audit-side');
  const btnAuditFullNew = document.getElementById('btn-audit-full-new');

  if (btnToggleAuditSide) {
    btnToggleAuditSide.addEventListener('click', () => {
      if (auditSidebar) {
        auditSidebar.classList.remove('is-narrow');
        auditSidebar.classList.add('is-wide');
        localStorage.setItem('audit_sidebar_state', 'wide');
      }
    });
  }

  if (btnCollapseAuditSide) {
    btnCollapseAuditSide.addEventListener('click', () => {
      if (auditSidebar) {
        auditSidebar.classList.remove('is-wide');
        auditSidebar.classList.add('is-narrow');
        localStorage.setItem('audit_sidebar_state', 'narrow');
      }
    });
  }

  if (btnAuditFullNew) {
    btnAuditFullNew.addEventListener('click', () => {
      if (homeTextarea) homeTextarea.value = '';
      window.location.hash = 'home';
    });
  }

  // Home Sidebar: Collapse to Narrow / Expand to Full Wide
  const btnExpandHomeSide = document.getElementById('btn-expand-home-side');
  const btnHomeNarrowNew = document.getElementById('btn-home-narrow-new');

  if (btnCloseHomeSide) {
    btnCloseHomeSide.addEventListener('click', () => {
      if (homeSidebar) {
        homeSidebar.classList.remove('is-wide');
        homeSidebar.classList.add('is-narrow');
        localStorage.setItem('home_sidebar_state', 'narrow');
      }
    });
  }

  if (btnExpandHomeSide) {
    btnExpandHomeSide.addEventListener('click', () => {
      if (homeSidebar) {
        homeSidebar.classList.remove('is-narrow');
        homeSidebar.classList.add('is-wide');
        localStorage.setItem('home_sidebar_state', 'wide');
      }
    });
  }

  if (btnHomeNarrowNew) {
    btnHomeNarrowNew.addEventListener('click', () => {
      if (homeTextarea) homeTextarea.value = '';
      window.location.hash = 'home';
    });
  }

  // Restore saved sidebar states (if any)
  if (localStorage.getItem('audit_sidebar_state') === 'wide') {
    if (auditSidebar) {
      auditSidebar.classList.remove('is-narrow');
      auditSidebar.classList.add('is-wide');
    }
  }
  if (localStorage.getItem('home_sidebar_state') === 'narrow') {
    if (homeSidebar) {
      homeSidebar.classList.remove('is-wide');
      homeSidebar.classList.add('is-narrow');
    }
  }

  const auditResizer = document.getElementById('audit-resizer');

  // Draggable Splitter between Chat and Live Audit Canvas
  const chatPane = document.querySelector('.view-audit .s64');
  const splitContainer = document.querySelector('.view-audit .split');

  if (auditResizer && chatPane && splitContainer) {
    let isDragging = false;
    let startX = 0;
    let startWidth = 0;

    // Restore saved width
    const savedWidth = localStorage.getItem('audit_chat_width_pct');
    if (savedWidth) {
      chatPane.style.flex = `0 0 ${savedWidth}`;
    }

    const startDrag = (clientX) => {
      isDragging = true;
      startX = clientX;
      startWidth = chatPane.getBoundingClientRect().width;
      auditResizer.classList.add('is-dragging');
      document.body.classList.add('resizing-col');
    };

    const doDrag = (clientX) => {
      if (!isDragging) return;
      const splitRect = splitContainer.getBoundingClientRect();
      const sidebar = document.querySelector('.view-audit .side');
      let sideWidth = 0;
      if (sidebar && sidebar.offsetParent !== null) {
        sideWidth = sidebar.getBoundingClientRect().width;
      }
      const availableWidth = splitRect.width - sideWidth - 10;
      const deltaX = clientX - startX;
      let newWidth = startWidth + deltaX;

      // Min chat width: 320px, Min canvas width: 360px
      const minW = 320;
      const maxW = availableWidth - 360;
      if (newWidth < minW) newWidth = minW;
      if (newWidth > maxW) newWidth = maxW;

      const pct = ((newWidth / availableWidth) * 100).toFixed(2);
      chatPane.style.flex = `0 0 ${pct}%`;
      localStorage.setItem('audit_chat_width_pct', `${pct}%`);
    };

    const stopDrag = () => {
      if (isDragging) {
        isDragging = false;
        auditResizer.classList.remove('is-dragging');
        document.body.classList.remove('resizing-col');
      }
    };

    auditResizer.addEventListener('mousedown', (e) => {
      startDrag(e.clientX);
      e.preventDefault();
    });

    window.addEventListener('mousemove', (e) => {
      if (isDragging) {
        doDrag(e.clientX);
      }
    });

    window.addEventListener('mouseup', stopDrag);

    auditResizer.addEventListener('touchstart', (e) => {
      if (e.touches && e.touches[0]) {
        startDrag(e.touches[0].clientX);
      }
    }, { passive: true });

    window.addEventListener('touchmove', (e) => {
      if (isDragging && e.touches && e.touches[0]) {
        doDrag(e.touches[0].clientX);
      }
    }, { passive: true });

    window.addEventListener('touchend', stopDrag);

    // Double-click to reset to default 46%
    auditResizer.addEventListener('dblclick', () => {
      chatPane.style.flex = '0 0 46%';
      localStorage.removeItem('audit_chat_width_pct');
    });
  }

  // ================= 8. HELPERS =================
  function escapeHtml(str) {
    if (!str) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  function formatMarkdown(text) {
    if (!text) return '';
    return text
      .replace(/\*\*(.*?)\*\*/g, '<b>$1</b>')
      .replace(/\*(.*?)\*/g, '<i>$1</i>')
      .replace(/`([^`]+)`/g, '<span class="pii">$1</span>')
      .replace(/\n\n/g, '<br><br>')
      .replace(/\n/g, '<br>');
  }

  // ================= 9. AI SYSTEM & RAG INSPECTOR =================
  function initSystemInspector() {
    const modal = document.getElementById('system-inspector-modal');
    const closeBtn = document.getElementById('btn-close-inspector');
    const openBtns = document.querySelectorAll('.btn-open-inspector');
    if (!modal) return;

    const tabs = modal.querySelectorAll('.inspector-tab');
    const panes = {
      obs: document.getElementById('inspector-pane-obs'),
      rag: document.getElementById('inspector-pane-rag'),
      ingest: document.getElementById('inspector-pane-ingest'),
    };

    const switchTab = (tabName) => {
      tabs.forEach(t => {
        const active = t.dataset.tab === tabName;
        t.classList.toggle('active', active);
        t.style.background = active ? '#0047FF' : '#fff';
        t.style.color = active ? '#fff' : '#334155';
        t.style.borderColor = active ? '#0047FF' : '#E2E8F0';
      });
      Object.entries(panes).forEach(([k, el]) => {
        if (el) el.style.display = k === tabName ? 'block' : 'none';
      });
      if (tabName === 'obs') loadObservability();
      if (tabName === 'rag') loadLawsList();
    };

    const loadObservability = async () => {
      const healthRow = document.getElementById('inspector-health-row');
      const kpiGrid = document.getElementById('inspector-kpi-grid');
      if (healthRow) healthRow.innerHTML = '<div style="grid-column:span 3;color:#64748B;font-size:13px;">Đang tải dữ liệu hệ thống...</div>';
      try {
        const res = await fetch('/api/health');
        const h = await res.json();
        const db = h.database || {};
        const cache = h.semantic_cache || {};
        const tel = h.telemetry || {};

        const cardStyle = 'padding:14px;border-radius:14px;border:1px solid #E2E8F0;background:#F8FAFC;';
        if (healthRow) {
          healthRow.innerHTML = `
            <div style="${cardStyle}">
              <div style="font-size:11px;color:#64748B;font-weight:600;text-transform:uppercase;">Database Engine</div>
              <div style="font-size:15px;font-weight:700;color:${db.status === 'healthy' ? '#059669' : '#DC2626'};margin-top:4px;">● ${escapeHtml(db.status || 'unknown')}</div>
              <div style="font-size:11px;color:#64748B;margin-top:2px;">${escapeHtml(db.engine || 'sqlalchemy')}</div>
            </div>
            <div style="${cardStyle}">
              <div style="font-size:11px;color:#64748B;font-weight:600;text-transform:uppercase;">Local Ollama (On-Prem)</div>
              <div style="font-size:15px;font-weight:700;color:${h.ollama_local === 'available' ? '#059669' : '#D97706'};margin-top:4px;">● ${escapeHtml(h.ollama_local || 'offline')}</div>
              <div style="font-size:11px;color:#64748B;margin-top:2px;">Hybrid LLM Failover</div>
            </div>
            <div style="${cardStyle}">
              <div style="font-size:11px;color:#64748B;font-weight:600;text-transform:uppercase;">Kho Luật Vector RAG</div>
              <div style="font-size:18px;font-weight:700;color:#0047FF;margin-top:4px;">${h.vector_rag_laws_count || 0} điều luật</div>
              <div style="font-size:11px;color:#64748B;margin-top:2px;">Đã lập chỉ mục Cosine</div>
            </div>
          `;
        }

        if (kpiGrid) {
          kpiGrid.innerHTML = `
            <div style="${cardStyle}">
              <div style="font-size:11px;color:#64748B;font-weight:600;">TỔNG REQUEST AI</div>
              <div style="font-size:20px;font-weight:700;color:#0F2147;margin-top:4px;">${tel.total_requests ?? 0}</div>
              <div style="font-size:11px;color:#64748B;">Độ trễ p95: <b>${tel.p95_latency_ms ?? 0} ms</b></div>
            </div>
            <div style="${cardStyle}">
              <div style="font-size:11px;color:#64748B;font-weight:600;">SEMANTIC CACHE HIT</div>
              <div style="font-size:20px;font-weight:700;color:#059669;margin-top:4px;">${cache.hit_rate_pct ?? 0}%</div>
              <div style="font-size:11px;color:#64748B;">${cache.hits ?? 0} hits / ${cache.total_entries ?? 0} mẫu</div>
            </div>
            <div style="${cardStyle}">
              <div style="font-size:11px;color:#64748B;font-weight:600;">CHI PHÍ &amp; TOKEN</div>
              <div style="font-size:20px;font-weight:700;color:#0F2147;margin-top:4px;">$${tel.estimated_total_cost_usd ?? 0}</div>
              <div style="font-size:11px;color:#059669;">Tiết kiệm Cache: <b>$${cache.saved_cost_usd ?? 0}</b></div>
            </div>
          `;
        }
      } catch (e) {
        if (healthRow) healthRow.innerHTML = '<div style="grid-column:span 3;color:#DC2626;font-size:13px;">Không tải được số liệu hệ thống.</div>';
      }
    };

    const loadLawsList = async () => {
      const listEl = document.getElementById('inspector-laws-list');
      const countEl = document.getElementById('inspector-laws-count');
      if (!listEl) return;
      try {
        const res = await fetch('/api/laws/list');
        const data = await res.json();
        if (countEl) countEl.textContent = data.total || 0;
        listEl.innerHTML = (data.laws || []).map(l => `
          <div style="padding:10px 12px;border-radius:12px;border:1px solid #EEF2F6;background:#FAFCFF;">
            <div style="display:flex;justify-content:space-between;align-items:center;gap:8px;">
              <b style="font-size:12.5px;color:#0F2147;">${escapeHtml(l.law_name)} · ${escapeHtml(l.article)}</b>
              <span style="font-size:11px;padding:2px 8px;border-radius:999px;background:#EFF6FF;color:#0047FF;font-weight:600;">${escapeHtml(l.category || 'law')}</span>
            </div>
            <div style="font-size:12px;color:#334155;font-weight:600;margin-top:3px;">${escapeHtml(l.title)}</div>
            <div style="font-size:11.5px;color:#64748B;margin-top:2px;">${escapeHtml(l.snippet)}</div>
          </div>
        `).join('');
      } catch (e) {
        listEl.innerHTML = '<div style="color:#DC2626;font-size:12px;">Lỗi tải danh sách luật.</div>';
      }
    };

    const runRagSearch = async () => {
      const qInput = document.getElementById('inspector-rag-query');
      const resBox = document.getElementById('inspector-rag-results');
      const q = qInput ? qInput.value.trim() : '';
      if (!q || !resBox) return;
      resBox.innerHTML = '<div style="font-size:12.5px;color:#64748B;">Đang truy xuất Vector RAG...</div>';
      try {
        const res = await fetch(`/api/laws/search?q=${encodeURIComponent(q)}&top_k=4`);
        const data = await res.json();
        if (!data.results || !data.results.length) {
          resBox.innerHTML = '<div style="font-size:12.5px;color:#64748B;">Không tìm thấy điều luật phù hợp.</div>';
          return;
        }
        resBox.innerHTML = data.results.map(r => `
          <div style="padding:11px 13px;border-radius:12px;border:1px solid #BFDBFE;background:#EFF6FF;">
            <div style="display:flex;justify-content:space-between;align-items:center;">
              <b style="font-size:13px;color:#0047FF;">⚖️ ${escapeHtml(r.law_name)} — ${escapeHtml(r.article)}</b>
              <span style="font-size:11px;font-weight:700;color:#059669;background:#DCFCE7;padding:2px 8px;border-radius:999px;">Độ khớp: ${Math.round((r.relevance_score || 0) * 100)}%</span>
            </div>
            <div style="font-size:12.5px;font-weight:600;color:#0F2147;margin-top:4px;">${escapeHtml(r.title)}</div>
            <div style="font-size:12px;color:#334155;margin-top:3px;line-height:1.45;">${escapeHtml((r.content || '').slice(0, 260))}...</div>
          </div>
        `).join('');
      } catch (e) {
        resBox.innerHTML = '<div style="color:#DC2626;font-size:12.5px;">Lỗi truy vấn Vector RAG.</div>';
      }
    };

    openBtns.forEach(btn => btn.addEventListener('click', () => {
      modal.style.display = 'flex';
      switchTab('obs');
    }));
    if (closeBtn) closeBtn.addEventListener('click', () => { modal.style.display = 'none'; });
    modal.addEventListener('click', (e) => { if (e.target === modal) modal.style.display = 'none'; });
    tabs.forEach(t => t.addEventListener('click', () => switchTab(t.dataset.tab)));

    const refreshBtn = document.getElementById('btn-inspector-refresh');
    if (refreshBtn) refreshBtn.addEventListener('click', loadObservability);

    const clearCacheBtn = document.getElementById('btn-inspector-clear-cache');
    if (clearCacheBtn) {
      clearCacheBtn.addEventListener('click', async () => {
        await fetch('/api/cache/clear', { method: 'POST' });
        loadObservability();
      });
    }

    const searchBtn = document.getElementById('btn-inspector-rag-search');
    const searchInput = document.getElementById('inspector-rag-query');
    if (searchBtn) searchBtn.addEventListener('click', runRagSearch);
    if (searchInput) searchInput.addEventListener('keydown', (e) => { if (e.key === 'Enter') runRagSearch(); });

    const uploadLawBtn = document.getElementById('btn-inspector-upload-law');
    const statusBox = document.getElementById('inspector-ingest-status');
    if (uploadLawBtn) {
      uploadLawBtn.addEventListener('click', async () => {
        const fileEl = document.getElementById('inspector-law-file');
        if (!fileEl || !fileEl.files.length) {
          if (statusBox) statusBox.textContent = '⚠️ Vui lòng chọn file văn bản luật trước.';
          return;
        }
        const fd = new FormData();
        fd.append('file', fileEl.files[0]);
        if (statusBox) statusBox.textContent = '⏳ Đang nạp và lập chỉ mục Vector...';
        try {
          const res = await fetch('/api/laws/upload', { method: 'POST', body: fd });
          const data = await res.json();
          if (res.ok) {
            if (statusBox) statusBox.textContent = `✅ Đã nạp thành công "${data.file_name}"! Tổng kho RAG: ${data.total_laws_in_db} điều luật.`;
            loadLawsList();
          } else {
            if (statusBox) statusBox.textContent = `❌ Lỗi: ${data.detail || 'Không thể nạp file'}`;
          }
        } catch (e) {
          if (statusBox) statusBox.textContent = '❌ Lỗi kết nối máy chủ.';
        }
      });
    }

    const syncUrlBtn = document.getElementById('btn-inspector-sync-url');
    if (syncUrlBtn) {
      syncUrlBtn.addEventListener('click', async () => {
        const urlEl = document.getElementById('inspector-law-url');
        const url = urlEl ? urlEl.value.trim() : '';
        if (!url) {
          if (statusBox) statusBox.textContent = '⚠️ Vui lòng nhập đường link URL văn bản luật.';
          return;
        }
        if (statusBox) statusBox.textContent = '⏳ Đang cào nội dung luật và đồng bộ Vector DB...';
        try {
          const res = await fetch('/api/laws/sync-url', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ url }),
          });
          const data = await res.json();
          if (res.ok) {
            if (statusBox) statusBox.textContent = `✅ Đồng bộ thành công! Đã thêm ${data.new_articles_added ?? 0} điều luật mới.`;
            loadLawsList();
          } else {
            if (statusBox) statusBox.textContent = `❌ Lỗi: ${data.detail || 'Không thể cào link'}`;
          }
        } catch (e) {
          if (statusBox) statusBox.textContent = '❌ Lỗi kết nối máy chủ.';
        }
      });
    }
  }

  // ================= STARTUP =================
  initModels();
  initSystemInspector();

  // Chuyển Tab Chat / Thẩm định trên màn hình điện thoại
  const auditViewEl = document.getElementById('audit');
  document.querySelectorAll('.mob-seg-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.mob-seg-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      if (auditViewEl) auditViewEl.setAttribute('data-mobile-pane', btn.dataset.pane || 'chat');
      window.scrollTo({ top: 0, behavior: 'smooth' });
    });
  });
  // Phân quyền RBAC UI: Mặc định ẩn tuyệt đối nút AI System & RAG, chỉ hiện khi Admin được xác thực
  document.querySelectorAll('.btn-open-inspector').forEach(btn => {
    btn.classList.remove('is-admin-visible');
  });
  fetch('/api/auth/me')
    .then(r => r.ok ? r.json() : null)
    .then(me => {
      if (!me) return;
      if (me.role === 'admin') {
        document.querySelectorAll('.btn-open-inspector').forEach(btn => {
          btn.classList.add('is-admin-visible');
          btn.style.display = '';
        });
      }
      if (!me.is_authenticated && typeof me.guest_remaining_uses === 'number') {
        document.querySelectorAll('.user-profile-slot .s23, .user-profile-slot .menu-user-email').forEach(el => {
          el.textContent = `Còn ${me.guest_remaining_uses}/${me.guest_limit || 3} lượt dùng thử`;
        });
      }
      // Đồng bộ lại tên thật từ Database (tránh bị sai tên thành tiền tố email khi đăng nhập ở InPrivate/máy mới)
      if (me.is_authenticated && me.name && me.email) {
        try {
          const raw = localStorage.getItem('securedoc_user');
          const cur = raw ? JSON.parse(raw) : {};
          if (cur.name !== me.name) {
            const parts = me.name.trim().split(/\s+/);
            const avatar = parts.length >= 2
              ? (parts[0][0] + parts[parts.length - 1][0]).toUpperCase()
              : me.name.slice(0, 2).toUpperCase();
            const updated = Object.assign({}, cur, { name: me.name, email: me.email, avatar });
            localStorage.setItem('securedoc_user', JSON.stringify(updated));
            if (typeof window.syncCurrentUserProfile === 'function') {
              window.syncCurrentUserProfile();
            }
          }
        } catch (e) {}
      }
    })
    .catch(() => {});
  loadSessions().then(() => {
    window.__securedocSessionCount = sessionsCache.length;
    if (typeof window.updateDynamicGreeting === 'function') {
      window.updateDynamicGreeting(undefined, sessionsCache.length);
    }
    if (window.location.hash === '#audit' && sessionsCache.length) {
      openSession(sessionsCache[0].id);
    }
  });

})();
