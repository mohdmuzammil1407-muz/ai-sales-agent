// SOURCE: widget/widget.js
// SYNC: always cp widget/widget.js
//       vide-frontend/public/widget.js after changes
// Last synced: 2026-04-29
(function () {
  "use strict";

  var scriptEl =
    document.currentScript ||
    (function () {
      var scripts = document.getElementsByTagName("script");
      return scripts[scripts.length - 1] || null;
    })();

  var globalConfig = window.VIDIO_CONFIG || {};
  var defaults = {
    apiUrl: "http://127.0.0.1:8000/api/v1/chat",
    agentName: "Vidio",
    agentSubtitle: "Ilmora Studios AI Assistant",
    agentAvatar: "🎬",
    userAvatar: "👤",
    theme: "dark",
    storageKey: "vidio_conversation_id",
    profileStorageKey: "vidio_user_profile",
    historyStorageKey: "vidio_chat_history",
    maxRetries: 2,
    retryDelayMs: 1200
  };

  function readConfigValue(dataKey, globalKey, fallback) {
    var dataValue = scriptEl ? scriptEl.getAttribute(dataKey) : null;
    if (dataValue !== null && dataValue !== "") {
      return dataValue;
    }
    if (globalConfig[globalKey] !== undefined && globalConfig[globalKey] !== null) {
      return globalConfig[globalKey];
    }
    return fallback;
  }

  var CONFIG = {
    apiUrl: readConfigValue("data-api-url", "apiUrl", defaults.apiUrl),
    agentName: readConfigValue("data-agent-name", "agentName", defaults.agentName),
    agentSubtitle: readConfigValue(
      "data-agent-subtitle",
      "agentSubtitle",
      defaults.agentSubtitle
    ),
    agentAvatar: readConfigValue("data-agent-avatar", "agentAvatar", defaults.agentAvatar),
    userAvatar: readConfigValue("data-user-avatar", "userAvatar", defaults.userAvatar),
    theme: readConfigValue("data-theme", "theme", defaults.theme),
    storageKey: globalConfig.storageKey || defaults.storageKey,
    profileStorageKey: globalConfig.profileStorageKey || defaults.profileStorageKey,
    historyStorageKey: globalConfig.historyStorageKey || defaults.historyStorageKey,
    maxRetries: Number(globalConfig.maxRetries || defaults.maxRetries),
    retryDelayMs: Number(globalConfig.retryDelayMs || defaults.retryDelayMs)
  };

  var state = {
    conversationId: null,
    profile: {
      name: "",
      email: "",
      phone: ""
    },
    awaitingField: null,
    identityStep: null,
    identityReady: false,
    identityLoading: false,
    isOpen: false,
    isTyping: false,
    messages: [],
    unreadCount: 0,
    hasSentFirstAnonymousMessage: false,
    pendingPostBootstrapMessage: null,
    queuedInitialMessage: "",
    pendingVerificationIdentifier: "",
    requireEmailVerification: false,
    suppressNextAuthGreeting: false,
    activeFlow: null,
    flowStep: null,
    meetingFlow: null,
    menuShown: false,
    errorState: null,
    pendingAction: null,
    isSending: false,
    hasShownWelcomeBack: false,
    slotGridRendered: false
  };


  var elements = {
    root: null,
    button: null,
    badge: null,
    window: null,
    messages: null,
    msgArea: null,
    menu: null,
    input: null,
    send: null,
    close: null,
    typing: null
  };

  function lsGet(key) {
    try {
      return window.localStorage.getItem(key);
    } catch (error) {
      return null;
    }
  }

  function lsSet(key, value) {
    try {
      window.localStorage.setItem(key, value);
    } catch (error) {
      return;
    }
  }

  function lsRemove(key) {
    try {
      window.localStorage.removeItem(key);
    } catch (error) {
      return;
    }
  }

  function escapeHtml(value) {
    return String(value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function normalizeName(raw) {
    return String(raw || "")
      .trim()
      .split(/\s+/)
      .filter(function (word) {
        return word;
      })
      .map(function (word) {
        return word.charAt(0).toUpperCase() + word.slice(1).toLowerCase();
      })
      .join(" ");
  }

  function formatMessageContent(content) {
    if (content.indexOf('class="vidio-retry-btn"') !== -1) {
      var marker = "[[RETRY_BUTTON]]";
      var safeContent = content.replace(
        /<button class="vidio-retry-btn"[^>]*>[\s\S]*?<\/button>/i,
        marker
      );
      return escapeHtml(safeContent)
        .replace(/\n/g, "<br>")
        .replace(marker, '<button class="vidio-retry-btn" type="button">Retry</button>');
    }

    return escapeHtml(content).replace(/\n/g, "<br>");
  }

  function persistConversationId(conversationId) {
    state.conversationId = conversationId;
    if (conversationId) {
      lsSet(CONFIG.storageKey, conversationId);
    } else {
      lsRemove(CONFIG.storageKey);
    }
  }

  function persistProfile() {
    lsSet(CONFIG.profileStorageKey, JSON.stringify(state.profile));
  }

  function getAuthApiBase() {
    return CONFIG.apiUrl.replace(/\/api\/v1\/chat(?:\?.*)?$/i, "");
  }

  function promoteProfileToAuthSession() {
    if (!state.profile.email && !state.profile.phone) {
      return;
    }

    lsSet(
      "vidio_auth_user",
      JSON.stringify({
        name: state.profile.name || "Member",
        email: state.profile.email || "",
        phone: state.profile.phone || "",
        authMethod: "password",
        token: window.btoa((state.profile.email || "member") + ":" + Date.now()),
        createdAt: new Date().toISOString()
      })
    );

    if (typeof VidioAuth !== "undefined") {
      window.dispatchEvent(
        new CustomEvent("vidio:auth:login", {
          detail: {
            name: state.profile.name || "Member",
            email: state.profile.email || "",
            phone: state.profile.phone || "",
            authMethod: "password"
          }
        })
      );
    }
  }

  function completeWidgetOtpSignIn(user) {
    var authUser = {
      name: user.name || state.profile.name || "Member",
      email: user.email || state.profile.email || "",
      phone: user.phone || state.profile.phone || "",
      authMethod: "otp",
      token:
        user.token ||
        window.btoa(
          ((user.email || state.profile.email || user.phone || state.profile.phone || "otp")) +
          ":" +
          Date.now()
        ),
      createdAt: new Date().toISOString()
    };

    lsSet("vidio_auth_user", JSON.stringify(authUser));
    lsSet("vidio_identity_verified", "1");

    window.dispatchEvent(
      new CustomEvent("vidio:auth:login", {
        detail: {
          name: authUser.name,
          email: authUser.email,
          phone: authUser.phone,
          authMethod: "otp",
          token: authUser.token,
          fromWidgetFlow: true
        }
      })
    );
  }

  function persistMessages() {
    lsSet(CONFIG.historyStorageKey, JSON.stringify(state.messages));
  }

  function restoreLocalState() {
    state.conversationId = lsGet(CONFIG.storageKey);

    try {
      var rawProfile = lsGet(CONFIG.profileStorageKey);
      if (rawProfile) {
        state.profile = JSON.parse(rawProfile);
      }
    } catch (error) {
      state.profile = { name: "", email: "", phone: "" };
    }
  }

  (function () {
    var hasProfile = !!lsGet("vidio_user_profile");
    var hasVerified = lsGet("vidio_identity_verified") === "1";
    var hasAuth = !!lsGet("vidio_auth_user");
    if (hasProfile && !hasVerified && !hasAuth) {
      lsRemove("vidio_user_profile");
      lsRemove("vidio_chat_history");
      lsRemove("vidio_conversation_id");
    }
  })();

  function injectStyles() {
    if (document.getElementById("vidio-widget-styles")) {
      return;
    }

    var href = "widget.css";
    if (scriptEl && scriptEl.src) {
      href = scriptEl.src.replace(/widget\.js(?:\?.*)?$/, "widget.css");
    }

    var link = document.createElement("link");
    link.id = "vidio-widget-styles";
    link.rel = "stylesheet";
    link.href = href;
    document.head.appendChild(link);
  }

  function getLocaleTimestamp(ts) {
    var date = ts instanceof Date ? ts : new Date(ts || Date.now());
    return date.toLocaleTimeString([], {
      hour: "numeric",
      minute: "2-digit"
    });
  }

  function scrollToBottom() {
    if (!elements.messages) {
      return;
    }

    elements.messages.scrollTo({
      top: elements.messages.scrollHeight,
      behavior: "smooth"
    });
  }

  function setPlaceholder(text) {
    if (elements.input) {
      elements.input.placeholder = text;
    }
  }

  function removeQuickReplies() {
    if (!elements.msgArea) {
      return;
    }

    var existing = elements.msgArea.querySelectorAll(".vidio-quick-replies, .vidio-quick-reply-btn");
    existing.forEach(function (el) {
      el.remove();
    });

    if (elements.menu) {
      elements.menu.classList.remove("is-open");
      elements.menu.setAttribute("aria-expanded", "false");
    }
  }

  function removeMeetingSlotButtons() {
    if (!elements.msgArea) {
      return;
    }

    var existing = elements.msgArea.querySelector(".vidio-slot-options");
    if (existing) {
      existing.remove();
    }
    state.slotGridRendered = false;
  }

  function removeMeetingDateButtons() {
    if (!elements.msgArea) {
      return;
    }

    var existing = elements.msgArea.querySelector(".vidio-date-options");
    if (existing) {
      existing.remove();
    }
  }

  function disableMeetingChoiceButtons(selector) {
    document.querySelectorAll(selector).forEach(function (btn) {
      btn.disabled = true;
      btn.style.opacity = "0.5";
      btn.style.cursor = "not-allowed";
      btn.style.pointerEvents = "none";
    });
  }

  function addTimeSlotGrid(times, dateLabel) {
    if (state.slotGridRendered) {
      return;
    }

    var existing = elements.msgArea.querySelector(".vidio-time-grid");
    if (existing) existing.remove();

    var wrapper = document.createElement("div");
    wrapper.className = "vidio-time-grid";
    state.slotGridRendered = true;

    times.forEach(function (label) {
      var btn = document.createElement("button");
      btn.className = "vidio-time-btn";
      btn.textContent = label;
      btn.dataset.slot = label;
      btn.addEventListener("click", function (e) {
        e.stopPropagation();
        e.preventDefault();
        disableMeetingChoiceButtons(".vidio-time-btn");
        state.slotGridRendered = false;
        wrapper.remove();
        addMessage("user", this.dataset.slot || label, null, true);
        sendMessage(this.dataset.slot || label, true);
      }, { once: true });
      wrapper.appendChild(btn);
    });

    elements.msgArea.appendChild(wrapper);
    scrollToBottom();
  }

  function parseMeetingSlots(content) {
    var text = String(content || "");
    var slotPattern = /(^|\n)(\d+)\.\s+([^\n]+)/g;
    var match;
    var slots = [];

    if (
      text.toLowerCase().indexOf("available slots") === -1 &&
      text.toLowerCase().indexOf("strategy call") === -1
    ) {
      return slots;
    }

    while ((match = slotPattern.exec(text))) {
      slots.push({
        value: match[2],
        label: match[3].trim()
      });
    }

    return slots;
  }

  function parseMeetingDateOptions(content) {
    var text = String(content || "");
    var datePattern = /(^|\n)(\d+)\.\s+([^\n]+)/g;
    var match;
    var dates = [];

    if (text.toLowerCase().indexOf("please select a date for your strategy call") === -1) {
      return dates;
    }

    while ((match = datePattern.exec(text))) {
      dates.push({
        value: match[2],
        label: match[3].trim()
      });
    }

    return dates;
  }

  function getMeetingSlotDisplayText(content) {
    var text = String(content || "");
    var slotStart = text.search(/(^|\n)\d+\.\s+/m);
    var cleaned = text;

    if (slotStart !== -1) {
      cleaned = text.slice(0, slotStart).trim();
    }

    cleaned = cleaned.replace(
      /\n*\s*Just reply with the number of your preferred slot[\s\S]*$/i,
      ""
    );

    return cleaned.trim();
  }

  function getMeetingDateDisplayText(content) {
    var text = String(content || "");
    var dateStart = text.search(/(^|\n)\d+\.\s+/m);
    var cleaned = text;

    if (dateStart !== -1) {
      cleaned = text.slice(0, dateStart).trim();
    }

    cleaned = cleaned.replace(/\n*\s*Reply with a number to choose your date\.[\s\S]*$/i, "");

    return cleaned.trim();
  }

  function addMeetingSlotButtons(messageGroup, content) {
    var slots = parseMeetingSlots(content);
    var inner;
    var wrapper;

    removeMeetingSlotButtons();

    if (!messageGroup || !slots.length) {
      return;
    }

    inner = messageGroup.querySelector(".vidio-msg-inner");
    if (!inner) {
      return;
    }

    wrapper = document.createElement("div");
    wrapper.className = "vidio-slot-options";
    state.slotGridRendered = true;

    slots.forEach(function (slot) {
      var btn = document.createElement("button");
      btn.className = "vidio-slot-btn";
      btn.type = "button";
      btn.textContent = slot.label;
      btn.dataset.slot = slot.value;
      btn.addEventListener("click", async function (e) {
        e.stopPropagation();
        e.preventDefault();
        disableMeetingChoiceButtons(".vidio-slot-btn");
        removeMeetingSlotButtons();
        addMessage("user", slot.label, null, true);
        sendMessage(this.dataset.slot || slot.value, true);
      }, { once: true });
      wrapper.appendChild(btn);
    });

    var noneBtn = document.createElement("button");
    noneBtn.className = "vidio-slot-btn vidio-slot-btn--ghost";
    noneBtn.type = "button";
    noneBtn.textContent = "None of these work";
    noneBtn.addEventListener("click", function (e) {
      e.stopPropagation();
      e.preventDefault();
      disableMeetingChoiceButtons(".vidio-slot-btn");
      removeMeetingSlotButtons();
      addMessage("user", "None of these work", null, true);
      sendMessage("none", true);
    }, { once: true });
    wrapper.appendChild(noneBtn);

    inner.appendChild(wrapper);
    scrollToBottom();
  }

  function addMeetingDateButtons(messageGroup, content) {
    var dates = parseMeetingDateOptions(content);
    var inner;
    var wrapper;

    removeMeetingDateButtons();

    if (!messageGroup || !dates.length) {
      return;
    }

    inner = messageGroup.querySelector(".vidio-msg-inner");
    if (!inner) {
      return;
    }

    wrapper = document.createElement("div");
    wrapper.className = "vidio-date-options";

    dates.forEach(function (date) {
      var btn = document.createElement("button");
      btn.className = "vidio-slot-btn vidio-date-btn";
      btn.type = "button";
      btn.textContent = date.label;
      btn.addEventListener("click", function () {
        disableMeetingChoiceButtons(".vidio-date-btn");
        removeMeetingDateButtons();
        addMessage("user", date.label, null, true);
        sendMessage(date.value, true);
      }, { once: true });
      wrapper.appendChild(btn);
    });

    var laterBtn = document.createElement("button");
    laterBtn.className = "vidio-slot-btn vidio-slot-btn--ghost vidio-date-btn";
    laterBtn.type = "button";
    laterBtn.textContent = "Later";
    laterBtn.addEventListener("click", function () {
      disableMeetingChoiceButtons(".vidio-date-btn");
      removeMeetingDateButtons();
      addMessage("user", "Later", null, true);
      sendMessage("later", true);
    }, { once: true });
    wrapper.appendChild(laterBtn);

    inner.appendChild(wrapper);
    scrollToBottom();
  }

  function getMainMenuOptions() {
    return [
      { label: "I need a video ad", value: "I need a video ad" },
      { label: "View packages and pricing", value: "View packages and pricing" },
      { label: "Talk to the team", value: "Talk to the team" },
      { label: "Something else", value: "Something else" },
      { label: "Restart chat", value: "Restart chat" }
    ];
  }

  function canOpenQuickMenu() {
    return state.identityStep === "done" && !state.identityLoading;
  }

  function isMainMenuQuickReply(value) {
    return getMainMenuOptions().some(function (item) {
      return item.value === value;
    });
  }

  function updateMenuButtonVisibility() {
    if (!elements.menu) {
      return;
    }

    var enabled = canOpenQuickMenu();
    elements.menu.disabled = !enabled;
    elements.menu.classList.toggle("is-disabled", !enabled);
  }

  function addQuickReplies(options) {
    if (!elements.msgArea) {
      return;
    }

    removeQuickReplies();

    var wrapper = document.createElement("div");
    wrapper.className = "vidio-quick-replies";

    options.forEach(function (opt) {
      var option = typeof opt === "string" ? { label: opt, value: opt } : opt;
      var btn = document.createElement("button");
      btn.className = "vidio-quick-reply-btn";
      btn.type = "button";
      btn.textContent = option.label;
      btn.addEventListener("click", async function () {
        // AGENT FIX: disable ALL buttons in this wrapper immediately on first click
        // (UI-level dedup). The network-level lock lives inside sendMessage() via
        // state.isSending, so we do NOT set it here — avoids blocking routeMenuSelection.
        if (btn.disabled) return;  // guard against rapid double-click before wrapper.remove() fires
        var allBtns = wrapper.querySelectorAll(".vidio-quick-reply-btn");
        allBtns.forEach(function (b) { b.disabled = true; });
        wrapper.remove();
        addMessage("user", option.label);
        if (state.meetingFlow && state.meetingFlow.active && !isMainMenuQuickReply(option.value)) {
          await safeRouteToActiveFlow(option.value);
          return;
        }
        routeMenuSelection(option.value);
      });
      wrapper.appendChild(btn);
    });

    elements.msgArea.appendChild(wrapper);
    scrollToBottom();
  }

  function showMainMenu() {
    if (state.menuShown) {
      updateMenuButtonVisibility();
      return;
    }

    state.menuShown = true;
    setTimeout(function () {
      if (!canOpenQuickMenu()) {
        return;
      }
      addMessage("assistant", "What would you like to do today?", null, false);
      setTimeout(function () {
        addQuickReplies(getMainMenuOptions());
      }, 400);
    }, 400);
    updateMenuButtonVisibility();
  }

  function openQuickMenu() {
    if (!canOpenQuickMenu()) {
      return;
    }

    if (elements.msgArea && elements.msgArea.querySelector(".vidio-quick-replies")) {
      removeQuickReplies();
      return;
    }

    addQuickReplies(getMainMenuOptions());
    if (elements.menu) {
      elements.menu.classList.add("is-open");
      elements.menu.setAttribute("aria-expanded", "true");
    }
    scrollToBottom();
  }

  function restartChatSession() {
    var displayName = state.profile.name || "there";

    removeQuickReplies();
    clearHistory();
    persistConversationId(null);
    state.activeFlow = null;
    state.flowStep = null;
    state.meetingFlow = null;
    state.menuShown = false;
    clearErrorState();
    state.isSending = false;          // AGENT FIX: clear send lock on restart
    state.hasShownWelcomeBack = false; // AGENT FIX: reset so next session shows greeting
    state.hasSentFirstAnonymousMessage = false;
    state.pendingPostBootstrapMessage =
      "Welcome back, " +
      displayName +
      ". Your chat has been restarted.";
    state.queuedInitialMessage = "";
    state.pendingVerificationIdentifier = "";
    state.requireEmailVerification = false;
    state.suppressNextAuthGreeting = false;
    state.identityReady = false;
    state.identityStep = "done";
    hideTypingIndicator();

    if (elements.input) {
      elements.input.value = "";
      elements.input.style.height = "40px";
    }

    bootstrapIdentity(false);
  }

  function routeMenuSelection(value) {
    clearErrorState();
    hideRetryButton();
    hideErrorBubble();
    // AGENT FIX: reset the isSending lock at the start of every menu route.
    // Flows that display UI directly (pricing, video type) never call sendMessage,
    // so the lock set by the quick-reply UI guard would otherwise stay stuck.
    state.isSending = false;
    switch (value) {
      case "Restart chat":
        restartChatSession();
        break;

      case "I need a video ad":
        state.activeFlow = "video_inquiry";
        state.flowStep = "ask_video_type";
        state.identityReady = false;
        setTimeout(function () {
          addMessage(
            "assistant",
            "Great choice. Let's figure out exactly what you need.\n\n" +
            "First, what kind of video are you looking to create?",
            null,
            false
          );
          setTimeout(function () {
            addQuickReplies([
              { label: "Product showcase", value: "Product showcase" },
              { label: "Food and restaurant ad", value: "Food and restaurant ad" },
              { label: "UGC or influencer style", value: "UGC influencer style" },
              { label: "Brand awareness film", value: "Brand awareness film" },
              { label: "Not sure, help me decide", value: "Help me decide video type" }
            ]);
          }, 400);
        }, 400);
        break;

      case "View packages and pricing":
        state.activeFlow = "pricing_inquiry";
        state.flowStep = "menu";
        state.identityReady = false;
        setTimeout(function () {
          addMessage(
            "assistant",
            "Happy to walk you through what we offer.\n\n" +
            "What would you like to explore?",
            null,
            false
          );
          setTimeout(function () {
            addQuickReplies([
              {
                label: "Explore video types and prices",
                value: "Explore video types and prices"
              },
              {
                label: "Explore monthly packages",
                value: "Explore monthly packages"
              }
            ]);
          }, 400);
        }, 400);
        break;

      case "Talk to the team":
        handleTalkToTeamFlow();
        break;

      case "Something else":
        state.activeFlow = "open_inquiry";
        state.flowStep = "clarify_need";
        state.identityReady = true;
        setTimeout(function () {
          addMessage(
            "assistant",
            "Of course. I'm here to help with anything Ilmora Studios related.\n\n" +
            "Go ahead and tell me what's on your mind.",
            null,
            false
          );
        }, 400);
        break;

      case "Product showcase":
        state.flowStep = "ask_product_detail";
        state.identityReady = true;
        setTimeout(function () {
          addMessage(
            "assistant",
            "Perfect. Product showcases are one of our strongest suits.\n\n" +
            "Tell me about your product. What is it, and what makes it special?",
            null,
            false
          );
        }, 400);
        break;

      case "Food and restaurant ad":
        state.flowStep = "ask_food_detail";
        state.identityReady = true;
        setTimeout(function () {
          addMessage(
            "assistant",
            "Food visuals are all about making people want it right away.\n\n" +
            "Tell me about your restaurant or food brand. What are you promoting?",
            null,
            false
          );
        }, 400);
        break;

      case "UGC influencer style":
        state.flowStep = "ask_ugc_detail";
        state.identityReady = true;
        setTimeout(function () {
          addMessage(
            "assistant",
            "UGC-style ads can work really well for social proof and conversions.\n\n" +
            "What product or service are you promoting, and who is your target audience?",
            null,
            false
          );
        }, 400);
        break;

      case "Brand awareness film":
        state.flowStep = "ask_brand_detail";
        state.identityReady = true;
        setTimeout(function () {
          addMessage(
            "assistant",
            "Brand films are where cinematic storytelling really comes through.\n\n" +
            "Tell me about your brand. What feeling do you want people to leave with after watching?",
            null,
            false
          );
        }, 400);
        break;

      case "Help me decide video type":
        state.flowStep = "discovery";
        state.identityReady = true;
        setTimeout(function () {
          addMessage(
            "assistant",
            "No problem. I can help narrow it down.\n\n" +
            "First, who is your target audience: general consumers, businesses, or a niche community?",
            null,
            false
          );
        }, 400);
        break;

      case "Explore video types and prices":
        state.flowStep = "video_type_prices";
        state.identityReady = true;
        setTimeout(function () {
          addMessage(
            "assistant",
            "Here's a quick breakdown of our video types and pricing:\n\n" +
            "Type 1 — Single character AI video\n" +
            "15 sec -> Rs. 1,199 | 30 sec -> Rs. 1,899\n\n" +
            "Type 2 — Two character conversion video\n" +
            "30 sec -> Rs. 3,999\n\n" +
            "Type 3 — Realistic 3D product animation\n" +
            "30 sec -> Rs. 5,499\n\n" +
            "Type 4 — Food and restaurant animation\n" +
            "30 sec -> Rs. 5,999\n\n" +
            "Type 5 — UGC ads with professional voiceover\n" +
            "30 sec -> Rs. 6,999\n\n" +
            "Type 6 — Voiceover visual storytelling\n" +
            "30 sec -> Rs. 6,999 | 45 sec -> Rs. 9,999 | 60 sec -> Rs. 12,999\n\n" +
            "Which type would you like to explore more deeply?",
            null,
            false
          );
        }, 400);
        break;

      case "Explore monthly packages":
        state.flowStep = "monthly_packages";
        state.identityReady = true;
        setTimeout(function () {
          addMessage(
            "assistant",
            "We currently offer two monthly subscription packages:\n\n" +
            "Starter Pack — Rs. 30,000 per month\n" +
            "5 AI videos, 15 custom images or posters, 2 revisions per video, HD export.\n\n" +
            "Growth Pack — Rs. 50,000 per month\n" +
            "10 AI videos, 30 custom images or posters, 3 revisions per video, dedicated account manager, priority turnaround, HD export.\n\n" +
            "If you need something outside those options, we can also create a custom package.\n\n" +
            "Which direction sounds closer to what you need?",
            null,
            false
          );
        }, 400);
        break;

      default:
        state.identityReady = true;
        sendMessage(value, true);
        break;
    }
  }

  function updateBadge() {
    if (!elements.badge) {
      return;
    }

    if (state.unreadCount > 0 && !state.isOpen) {
      elements.badge.textContent = String(state.unreadCount);
      elements.badge.classList.remove("is-hidden");
    } else {
      elements.badge.textContent = "";
      elements.badge.classList.add("is-hidden");
    }
  }

  function updateComposerState() {
    if (!elements.input || !elements.send) {
      return;
    }

    if (state.identityStep === "ask_name") {
      elements.input.placeholder = "Type your name...";
    } else if (state.identityStep === "ask_email") {
      elements.input.placeholder = "Email or phone number...";
    } else if (state.identityStep === "ask_email_for_meeting") {
      elements.input.placeholder = "Your email address...";
    } else if (state.identityStep === "verify_otp" || state.identityStep === "ask_otp") {
      elements.input.placeholder = "Enter 6-digit code...";
    } else {
      elements.input.placeholder = "Type your message...";
    }

    elements.input.disabled = state.identityLoading;
    elements.send.disabled = state.identityLoading;
    elements.send.style.opacity = state.identityLoading ? "0.68" : "1";
    updateMenuButtonVisibility();
  }

  function addMessage(role, content, ts, save) {
    var messageTs = ts || new Date().toISOString();
    var shouldSave = save !== false;
    var displayContent = String(content || "");

    if (!elements.messages) {
      return null;
    }

    if (role === "assistant") {
      displayContent = displayContent
        .replace(/[\uD800-\uDBFF][\uDC00-\uDFFF]/g, "")
        .replace(/\uFE0F/g, "")
        .replace(/ {2,}/g, " ")
        .replace(/[ \t]+\n/g, "\n")
        .trim();
    }

    var group = document.createElement("div");
    group.className = "vidio-message-group vidio-message-group--" + role;
    group.setAttribute("data-role", role);
    group.setAttribute("data-ts", messageTs);

    var avatar = document.createElement("div");
    avatar.className =
      "vidio-avatar vidio-avatar--sm vidio-avatar--" +
      (role === "assistant" ? "agent" : "user");
    avatar.textContent = role === "assistant" ? CONFIG.agentAvatar : CONFIG.userAvatar;

    var inner = document.createElement("div");
    inner.className = "vidio-msg-inner";

    var bubble = document.createElement("div");
    bubble.className = "vidio-bubble vidio-bubble--" + role;

    if (role === "assistant" && displayContent.indexOf("TIMESLOTS::") !== -1) {
      var tsIndex = displayContent.indexOf("TIMESLOTS::");
      var textBefore = displayContent.substring(0, tsIndex).trim();
      var tsContent = displayContent.substring(tsIndex);
      var parts = tsContent.split("::");
      var dateLabel = parts[1] || "";
      var times = [];
      try {
        times = JSON.parse(parts[2] || "[]");
      } catch (err) {
        times = (parts[2] || "")
          .replace(/[\[\]"]/g, "")
          .split(",")
          .map(function (item) { return item.trim(); })
          .filter(Boolean);
      }

      var displayPrefix = textBefore ? formatMessageContent(textBefore) + "<br><br>" : "";
      bubble.innerHTML = times.length
        ? displayPrefix +
          "Great! Here are available times for <strong>" +
          escapeHtml(dateLabel) +
          "</strong>:"
        : "No slots available for this date. Please pick another date.";

      var timestamp = document.createElement("span");
      timestamp.className = "vidio-timestamp";
      timestamp.textContent = getLocaleTimestamp(messageTs);

      inner.appendChild(bubble);
      inner.appendChild(timestamp);
      group.appendChild(avatar);
      group.appendChild(inner);
      elements.messages.appendChild(group);

      if (times.length) {
        setTimeout(function () {
          addTimeSlotGrid(times, dateLabel);
        }, 300);
      }

      scrollToBottom();

      if (shouldSave) {
        state.messages.push({
          role: role,
          content: displayContent,
          ts: messageTs
        });
        persistMessages();
      }
      return group;
    }

    var dateOptions = role === "assistant" ? parseMeetingDateOptions(displayContent) : [];
    if (dateOptions.length) {
      displayContent = getMeetingDateDisplayText(displayContent);
    }

    bubble.innerHTML = formatMessageContent(displayContent);

    var timestamp = document.createElement("span");
    timestamp.className = "vidio-timestamp";
    timestamp.textContent = getLocaleTimestamp(messageTs);

    inner.appendChild(bubble);
    inner.appendChild(timestamp);

    if (role === "user") {
      group.appendChild(inner);
      group.appendChild(avatar);
    } else {
      group.appendChild(avatar);
      group.appendChild(inner);
    }

    elements.messages.appendChild(group);

    if (shouldSave) {
      state.messages.push({
        role: role,
        content: displayContent,
        ts: messageTs
      });
      persistMessages();
    }

    if (dateOptions.length) {
      addMeetingDateButtons(group, content);
    }



    scrollToBottom();
    return group;
  }

  function restoreHistory() {
    var history = [];

    try {
      history = JSON.parse(lsGet(CONFIG.historyStorageKey) || "[]");
    } catch (error) {
      history = [];
    }

    if (!Array.isArray(history) || history.length === 0) {
      state.messages = [];
      return false;
    }

    history.forEach(function (message) {
      if (!message || !message.role || !message.content) {
        return;
      }
      addMessage(message.role, message.content, message.ts, false);
    });

    state.messages = history;
    return true;
  }

  function clearHistory() {
    if (elements.msgArea) {
      elements.msgArea.innerHTML = "";
    }
    state.messages = [];
    lsRemove(CONFIG.historyStorageKey);
    removeMeetingSlotButtons();
  }

  function removeMessageByTs(ts) {
    state.messages = state.messages.filter(function (message) {
      return message.ts !== ts;
    });
    persistMessages();
  }

  function hideRetryButton() {
    if (!elements.msgArea) {
      return;
    }
    var retryButtons = elements.msgArea.querySelectorAll(".vidio-retry-btn");
    retryButtons.forEach(function (btn) {
      btn.style.display = "none";
    });
  }

  function hideErrorBubble() {
    if (!elements.msgArea) {
      return;
    }
    var groups = elements.msgArea.querySelectorAll(".vidio-message-group--assistant");
    groups.forEach(function (group) {
      var bubble = group.querySelector(".vidio-bubble--assistant");
      if (!bubble) {
        return;
      }
      if (bubble.textContent && bubble.textContent.indexOf("Having trouble connecting.") !== -1) {
        group.remove();
      }
    });
  }

  function clearErrorState() {
    state.errorState = null;
    state.pendingAction = null;
  }

  function attachRetryHandler(messageGroup, originalText, ts) {
    if (!messageGroup) {
      return;
    }

    var retryButton = messageGroup.querySelector(".vidio-retry-btn");
    if (!retryButton) {
      return;
    }

    retryButton.addEventListener("click", function () {
      var pendingAction = state.pendingAction;
      clearErrorState();
      hideRetryButton();
      hideErrorBubble();
      if (messageGroup.parentNode) {
        messageGroup.parentNode.removeChild(messageGroup);
      }
      removeMessageByTs(ts);
      showTypingIndicator();
      window.setTimeout(function () {
        hideTypingIndicator();
        if (pendingAction === "talk_to_team") {
          handleTalkToTeamFlow();
          return;
        }
        handleSend(originalText);
      }, 120);
    });
  }

  function isIdentityVerified() {
    return state.identityStep === "done" || lsGet("vidio_identity_verified") === "1";
  }

  function isTalkToTeamRequest(value) {
    return false;
  }

  function handleTalkToTeamFlow() {
    var authUser = typeof VidioAuth !== "undefined" && VidioAuth.getUser ? VidioAuth.getUser() : null;
    var knownEmail = state.profile.email || (authUser && authUser.email) || null;
    state.activeFlow = "meeting_local";
    state.meetingFlow = {
      active: true,
      step: "NAME",
      userName: state.profile.name || null,
      userEmail: knownEmail,
      meetingPurpose: null,
      preferredTime: null
    };

    if (state.meetingFlow.userName) {
      if (knownEmail && isIdentityVerified()) {
        state.meetingFlow.step = "PURPOSE";
      } else if (knownEmail && !isIdentityVerified()) {
        state.meetingFlow.step = "EMAIL";
      } else {
        state.meetingFlow.step = "EMAIL";
      }
    }
    state.flowStep = state.meetingFlow.step;

    if (state.meetingFlow.userName && state.meetingFlow.userEmail) {
      addMessage(
        "assistant",
        "Great, " +
        state.meetingFlow.userName +
        "! Let's get you connected with the Ilmora Studios team. 🎬\n" +
        "What would you like to discuss with the team?",
        null,
        false
      );
    } else if (state.meetingFlow.userName) {
      addMessage(
        "assistant",
        "Great, " +
        state.meetingFlow.userName +
        "! Let's get you connected with the Ilmora Studios team. 🎬\n" +
        "What's your email address to reach you?",
        null,
        false
      );
    } else {
      addMessage(
        "assistant",
        "Great! Let's get you connected with the Ilmora Studios team. 🎬\n" +
        "First, what's your name?",
        null,
        false
      );
    }
  }

  function getCurrentStepQuestion() {
    var step = state.meetingFlow && state.meetingFlow.step;
    if (step === "NAME") return "what's your name?";
    if (step === "EMAIL") return "what's your email address?";
    if (step === "PURPOSE") return "what would you like to discuss with the team?";
    return "please continue with the current scheduling step.";
  }

  async function routeToActiveFlow(input) {
    var flow = state.meetingFlow;
    var trimmed = String(input || "").trim();
    if (!flow || !flow.active) {
      return false;
    }

    var normalized = trimmed.toLowerCase();
    if (
      normalized === "restart chat" ||
      normalized === "something else" ||
      normalized === "i need a video ad" ||
      normalized === "view packages and pricing" ||
      normalized === "talk to the team"
    ) {
      routeMenuSelection(
        normalized === "restart chat"
          ? "Restart chat"
          : normalized === "something else"
            ? "Something else"
            : normalized === "i need a video ad"
              ? "I need a video ad"
              : normalized === "view packages and pricing"
                ? "View packages and pricing"
                : "Talk to the team"
      );
      return true;
    }

    switch (flow.step) {
      case "NAME":
        if (!trimmed) {
          addMessage("assistant", "Please share your name so I can continue.", null, false);
          return true;
        }
        flow.userName = normalizeName(trimmed);
        state.profile.name = flow.userName;
        persistProfile();
        if (flow.userEmail) {
          flow.step = "PURPOSE";
          state.flowStep = "PURPOSE";
          addMessage("assistant", "Nice to meet you, " + flow.userName + "! 👋\nWhat would you like to discuss with the team?", null, false);
          return true;
        }
        flow.step = "EMAIL";
        state.flowStep = "EMAIL";
        addMessage("assistant", "Nice to meet you, " + flow.userName + "! 👋\nWhat's your email address?", null, false);
        return true;

      case "EMAIL":
        if (!isValidEmail(trimmed)) {
          addMessage("assistant", "Hmm, that doesn't look right. Could you re-enter your email?", null, false);
          return true;
        }
        flow.userEmail = trimmed.toLowerCase();
        state.profile.email = flow.userEmail;
        persistProfile();
        flow.step = "PURPOSE";
        state.flowStep = "PURPOSE";
        addMessage("assistant", "What would you like to discuss with the team?", null, false);
        return true;

      case "PURPOSE":
        if (!trimmed) {
          addMessage("assistant", "What would you like to discuss with the team?", null, false);
          return true;
        }
        flow.meetingPurpose = trimmed;
        // Keep flow alive so date/slot rendering triggers on backend reply
        state.activeFlow = "meeting_local";
        state.meetingFlow = null;
        state.flowStep = "AWAITING_DATE";
        state.isSending = false;
        sendMessage(trimmed, true, {
          activeFlow: "meeting_local",
          flowStep: "PURPOSE"
        });
        return true;

      default:
        addMessage("assistant", "Just to confirm — " + getCurrentStepQuestion(), null, false);
        return true;
    }
  }

  async function safeRouteToActiveFlow(input) {
    try {
      return await routeToActiveFlow(input);
    } catch (err) {
      hideTypingIndicator();
      console.warn("[Vidio] routeToActiveFlow error:", err);
      addMessage("assistant", "Let's continue — " + getCurrentStepQuestion(), null, false);
      return true;
    }
  }

  function showTypingIndicator() {
    if (!elements.messages || state.isTyping) {
      return;
    }

    state.isTyping = true;

    var group = document.createElement("div");
    group.className = "vidio-message-group vidio-message-group--assistant";
    group.id = "vidio-widget-typing";

    var avatar = document.createElement("div");
    avatar.className = "vidio-avatar vidio-avatar--sm vidio-avatar--agent";
    avatar.textContent = CONFIG.agentAvatar;

    var bubbleWrap = document.createElement("div");
    bubbleWrap.className = "vidio-typing-bubbles";

    for (var i = 0; i < 3; i += 1) {
      var dot = document.createElement("span");
      dot.className = "vidio-typing-dot";
      bubbleWrap.appendChild(dot);
    }

    group.appendChild(avatar);
    group.appendChild(bubbleWrap);
    elements.typing = group;
    elements.messages.appendChild(group);
    scrollToBottom();
  }

  function hideTypingIndicator() {
    state.isTyping = false;

    if (elements.typing && elements.typing.parentNode) {
      elements.typing.parentNode.removeChild(elements.typing);
    }

    elements.typing = null;
  }

  function isValidEmail(value) {
    var email = String(value || "").trim().toLowerCase();
    var disposableDomains = {
      "mailinator.com": true,
      "guerrillamail.com": true,
      "tempmail.com": true,
      "throwaway.email": true,
      "yopmail.com": true,
      "sharklasers.com": true,
      "grr.la": true,
      "trashmail.com": true,
      "maildrop.cc": true,
      "fakeinbox.com": true,
      "mailnesia.com": true,
      "discard.email": true
    };
    var domain = email.split("@").pop();
    return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email) && !disposableDomains[domain];
  }

  function isValidPhone(value) {
    return String(value || "")
      .replace(/[^\d]/g, "")
      .length >= 7;
  }

  function isSkipPhone(value) {
    var normalized = String(value || "").trim().toLowerCase();
    return ["skip", "no", "nope", "skip it", "next", "continue", "pass"].indexOf(normalized) !== -1;
  }

  function isOtpResend(value) {
    var normalized = String(value || "").trim().toLowerCase();
    return ["resend", "send again", "resend code", "send code again"].indexOf(normalized) !== -1;
  }

  function fetchWithRetry(url, payload, onSuccess, onError, attempt) {
    var currentAttempt = attempt || 1;

    fetch(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify(payload)
    })
      .then(function (response) {
        if (!response.ok) {
          throw new Error("Request failed with status " + response.status);
        }
        return response.json();
      })
      .then(function (data) {
        onSuccess(data);
      })
      .catch(function (error) {
        if (currentAttempt <= CONFIG.maxRetries) {
          window.setTimeout(function () {
            fetchWithRetry(url, payload, onSuccess, onError, currentAttempt + 1);
          }, CONFIG.retryDelayMs * currentAttempt);
          return;
        }

        onError(error && error.message ? error.message : "Request failed");
      });
  }

  function authRequestWithRetry(path, payload, onSuccess, onError, attempt) {
    var currentAttempt = attempt || 1;

    fetch(getAuthApiBase() + path, {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify(payload)
    })
      .then(function (response) {
        return response
          .json()
          .catch(function () {
            return {};
          })
          .then(function (data) {
            if (!response.ok) {
              throw new Error(data.detail || data.message || "Request failed");
            }
            return data;
          });
      })
      .then(function (data) {
        onSuccess(data);
      })
      .catch(function (error) {
        if (currentAttempt <= CONFIG.maxRetries) {
          window.setTimeout(function () {
            authRequestWithRetry(path, payload, onSuccess, onError, currentAttempt + 1);
          }, CONFIG.retryDelayMs * currentAttempt);
          return;
        }

        onError(error && error.message ? error.message : "Request failed");
      });
  }

  function requestIdentityOtp(identifier) {
    state.identityLoading = true;
    updateComposerState();
    showTypingIndicator();

    if (typeof VidioAuth !== "undefined" && typeof VidioAuth.requestOtp === "function") {
      VidioAuth.requestOtp(identifier)
        .then(function (result) {
          hideTypingIndicator();
          state.identityLoading = false;

          if (!result || result.success !== true) {
            addMessage(
              "assistant",
              (result && result.error) || "I could not send the verification code. Please try again.",
              null,
              false
            );
            updateComposerState();
            return;
          }

          if (result.delivery === "phone_pending") {
            state.requireEmailVerification = true;
            state.identityStep = "ask_email";
            addMessage(
              "assistant",
              "Phone verification is not available yet. Please share an email address to continue.",
              null,
              false
            );
            updateComposerState();
            return;
          }

          state.requireEmailVerification = false;
          state.identityStep = "verify_otp";
          state.pendingVerificationIdentifier = identifier;
          addMessage(
            "assistant",
            "A 6-digit verification code has been sent to " +
            identifier +
            ". Enter the code here to continue.",
            null,
            false
          );
          updateComposerState();
        })
        .catch(function () {
          hideTypingIndicator();
          state.identityLoading = false;
          addMessage(
            "assistant",
            "I could not send the verification code. Please try again.",
            null,
            false
          );
          updateComposerState();
        });
      return;
    }

    authRequestWithRetry(
      "/api/v1/auth/otp/request",
      {
        identifier: identifier,
        name: state.profile.name || null
      },
      function (data) {
        hideTypingIndicator();
        state.identityLoading = false;

        if (data && data.delivery === "phone_pending") {
          state.requireEmailVerification = true;
          state.identityStep = "ask_email";
          addMessage(
            "assistant",
            "Phone verification is not available yet. Please share an email address to continue.",
            null,
            false
          );
          updateComposerState();
          return;
        }

        state.requireEmailVerification = false;
        state.identityStep = "verify_otp";
        state.pendingVerificationIdentifier = identifier;
        addMessage(
          "assistant",
          "A 6-digit verification code has been sent to " +
          identifier +
          ". Enter the code here to continue.",
          null,
          false
        );
        updateComposerState();
      },
      function (errorMessage) {
        hideTypingIndicator();
        state.identityLoading = false;
        addMessage(
          "assistant",
          errorMessage || "I could not send the verification code. Please try again.",
          null,
          false
        );
        updateComposerState();
      },
      1
    );
  }

  function verifyIdentityOtp(otp) {
    state.identityLoading = true;
    updateComposerState();
    showTypingIndicator();

    if (typeof VidioAuth !== "undefined" && typeof VidioAuth.verifyOtp === "function") {
      state.suppressNextAuthGreeting = true;
      VidioAuth.verifyOtp(
        state.pendingVerificationIdentifier,
        otp,
        state.profile.name || null
      )
        .then(function (result) {
          hideTypingIndicator();
          state.identityLoading = false;

          if (!result || result.success !== true) {
            addMessage(
              "assistant",
              "That code was not valid. Please enter the 6-digit code again or type 'resend'.",
              null,
              false
            );
            updateComposerState();
            return;
          }

          state.identityStep = "done";
          state.profile.name = (result.user && result.user.name) || state.profile.name || "";
          state.profile.email = (result.user && result.user.email) || state.profile.email || "";
          state.profile.phone = (result.user && result.user.phone) || state.profile.phone || "";
          persistProfile();
          updateComposerState();
        })
        .catch(function () {
          state.suppressNextAuthGreeting = false;
          hideTypingIndicator();
          state.identityLoading = false;
          addMessage(
            "assistant",
            "That code was not valid. Please enter the 6-digit code again or type 'resend'.",
            null,
            false
          );
          updateComposerState();
        });
      return;
    }

    authRequestWithRetry(
      "/api/v1/auth/otp/verify",
      {
        identifier: state.pendingVerificationIdentifier,
        otp: otp,
        name: state.profile.name || null
      },
      function (data) {
        hideTypingIndicator();
        state.identityLoading = false;
        state.identityStep = "done";
        state.profile.name = (data.user && data.user.name) || state.profile.name || "";
        state.profile.email = (data.user && data.user.email) || state.profile.email || "";
        state.profile.phone = (data.user && data.user.phone) || state.profile.phone || "";
        persistProfile();
        completeWidgetOtpSignIn({
          name: state.profile.name,
          email: state.profile.email,
          phone: state.profile.phone,
          token: data.token
        });
        updateComposerState();
      },
      function () {
        hideTypingIndicator();
        state.identityLoading = false;
        addMessage(
          "assistant",
          "That code was not valid. Please enter the 6-digit code again or type 'resend'.",
          null,
          false
        );
        updateComposerState();
      },
      1
    );
  }

  function bootstrapIdentity(isReturningUser) {
    state.identityLoading = true;
    updateComposerState();
    updateMenuButtonVisibility();
    showTypingIndicator();

    var payload = {
      message: "identity bootstrap",
      conversation_id: state.conversationId,
      name: state.profile.name || null,
      email: state.profile.email || null,
      phone: state.profile.phone || null,
      active_flow: state.activeFlow || null,
      flow_step: state.flowStep || null,
      bootstrap_identity: true
    };

    fetchWithRetry(
      CONFIG.apiUrl,
      payload,
      function (data) {
        var conversationId =
          data.conversation_id || data.conversationId || state.conversationId;

        if (conversationId) {
          persistConversationId(conversationId);
        }

        hideTypingIndicator();
        state.identityLoading = false;
        state.identityReady = true;
        state.identityStep = "done";
        persistProfile();
        lsSet("vidio_identity_verified", "1");

        if (
          (state.profile.email || state.profile.phone) &&
          typeof VidioAuth !== "undefined" &&
          !VidioAuth.isLoggedIn()
        ) {
          promoteProfileToAuthSession();
        }

        if (state.pendingPostBootstrapMessage) {
          addMessage("assistant", state.pendingPostBootstrapMessage, null, false);
          state.pendingPostBootstrapMessage = null;
        }

        if (state.queuedInitialMessage) {
          var queuedMessage = state.queuedInitialMessage;
          state.queuedInitialMessage = "";
          window.setTimeout(function () {
            sendMessage(queuedMessage, true);
          }, 120);
        }

        if (
          isReturningUser &&
          state.isOpen &&
          !state.messages.length &&
          data.reply
        ) {
          addMessage("assistant", data.reply, null, false);
        }

        showMainMenu();

        updateComposerState();
        updateMenuButtonVisibility();
      },
      function () {
        // AGENT FIX: bootstrap error handler — profile sync failure must NEVER
        // block the user. Show menu, release all locks, let chat proceed normally.
        hideTypingIndicator();
        state.identityLoading = false;
        state.isSending = false;   // AGENT FIX: clear send lock in case it was set
        state.identityReady = true;
        state.profile.name = normalizeName(state.profile.name || "") || "there";
        state.identityStep =
          state.profile.email || state.profile.phone ? "done" : state.identityStep;
        // AGENT FIX: suppressed alarming 'could not sync' message for returning users;
        // log to console only so we can debug without confusing the user
        console.warn("[Vidio] Bootstrap profile sync failed — continuing without server sync.");
        updateComposerState();
        updateMenuButtonVisibility();
        // AGENT FIX: MUST call showMainMenu() here — without this, the widget
        // renders no options after a sync failure and appears completely frozen
        showMainMenu();
      },
      1
    );
  }

  function toggleWidget() {
    state.isOpen = !state.isOpen;

    if (!elements.window || !elements.button) {
      return;
    }

    elements.window.classList.toggle("is-visible", state.isOpen);
    elements.window.classList.toggle("is-hidden", !state.isOpen);
    elements.button.setAttribute("aria-expanded", state.isOpen ? "true" : "false");

    if (state.isOpen && state.unreadCount > 0) {
      state.unreadCount = 0;
      updateBadge();
    }

    if (state.isOpen && elements.input) {
      elements.input.focus();
      scrollToBottom();
    } else {
      updateBadge();
    }
  }

  function addRetryableErrorMessage(originalText) {
    var errorTs = new Date().toISOString();
    var group = addMessage(
      "assistant",
      'Having trouble connecting. <button class="vidio-retry-btn" type="button">Retry</button>',
      errorTs,
      true
    );
    state.errorState = "network_error";
    state.pendingAction =
      String(originalText || "").toLowerCase().indexOf("schedule a call with the team") !== -1
        ? "talk_to_team"
        : "message_send";

    attachRetryHandler(group, originalText, errorTs);

    if (!state.isOpen) {
      state.unreadCount += 1;
      updateBadge();
    }
  }

  function sendMessage(text, skipUserRender, flowOverrides) {
    var trimmed = String(text || "").trim();
    clearErrorState();
    hideRetryButton();
    hideErrorBubble();

    // AGENT FIX: double-guard with isSending lock in addition to identityLoading check
    if (!trimmed || state.identityLoading || state.isSending) {
      return;
    }
    state.isSending = true;

    if (elements.input) {
      elements.input.value = "";
      elements.input.style.height = "40px";
    }

    if (!skipUserRender) {
      addMessage("user", trimmed, null, true);
    }
    showTypingIndicator();

    fetchWithRetry(
      CONFIG.apiUrl,
      {
        message: trimmed,
        conversation_id: state.conversationId,
        name: state.profile.name || null,
        email: state.profile.email || null,
        phone: state.profile.phone || null,
        active_flow:
          flowOverrides && Object.prototype.hasOwnProperty.call(flowOverrides, "activeFlow")
            ? flowOverrides.activeFlow
            : state.activeFlow || null,
        flow_step:
          flowOverrides && Object.prototype.hasOwnProperty.call(flowOverrides, "flowStep")
            ? flowOverrides.flowStep
            : state.flowStep || null
      },
      function (data) {
        var conversationId =
          data.conversation_id || data.conversationId || state.conversationId;
        var reply =
          data.reply ||
          data.response ||
          data.message ||
          "Thanks for your message. How can I help next?";
        var slotOptions = parseMeetingSlots(reply);
        var displayReply = slotOptions.length ? getMeetingSlotDisplayText(reply) : reply;

        if (conversationId) {
          persistConversationId(conversationId);
        }

        hideTypingIndicator();
        state.isSending = false; // AGENT FIX: release lock on success
        if (data.suppress === true) {
          return;
        }
        var assistantGroup = addMessage("assistant", displayReply, null, true);
        addMeetingSlotButtons(assistantGroup, reply);

        if (data.meeting_needs_email) {
          state.identityStep = "ask_email_for_meeting";
          setPlaceholder("Your email address…");
          updateComposerState();
        }

        if (!state.isOpen) {
          state.unreadCount += 1;
          updateBadge();
        }
      },
      function () {
        hideTypingIndicator();
        state.isSending = false; // AGENT FIX: release lock on error too
        addRetryableErrorMessage(trimmed);
      },
      1
    );
  }

  async function handleSend(text) {
    var trimmed = String(text || "").trim();
    var verificationIdentifier = state.profile.email || state.profile.phone || "";
    clearErrorState();
    hideRetryButton();
    hideErrorBubble();

    if (!trimmed) {
      return;
    }

    if (trimmed.toLowerCase() === "restart chat") {
      restartChatSession();
      return;
    }

    if (state.meetingFlow && state.meetingFlow.active) {
      if (state.isSending) {
        return;
      }
      state.isSending = true;
      try {
        if (elements.input) {
          elements.input.value = "";
        }
        addMessage("user", trimmed, null, true);
        await safeRouteToActiveFlow(trimmed);
      } finally {
        state.isSending = false;
      }
      return;
    }

    if (isTalkToTeamRequest(trimmed)) {
      if (elements.input) {
        elements.input.value = "";
      }
      addMessage("user", trimmed, null, true);
      handleTalkToTeamFlow();
      return;
    }

    // AGENT FIX: for returning users (identityStep === 'done'), bootstrap loading
    // must NOT silently drop their messages. Only hard-block anonymous identity steps.
    // Previously this was a blanket 'if (identityLoading) return' that ate messages.
    var isIdentityFlowStep = (
      state.identityStep === "ask_name" ||
      state.identityStep === "ask_email" ||
      state.identityStep === "ask_otp" ||
      state.identityStep === "verify_otp" ||
      state.identityStep === "ask_email_for_meeting"
    );
    if (state.identityLoading && isIdentityFlowStep) {
      // Still collecting identity — block until step completes
      return;
    }
    // If identityLoading but step='done', it's just a non-blocking bootstrap sync.
    // Fall through and let the message be processed.

    if (state.identityStep === "ask_name") {
      if (elements.input) {
        elements.input.value = "";
      }
      addMessage("user", trimmed, null, true);
      state.profile.name = normalizeName(trimmed);
      state.requireEmailVerification = false;
      persistProfile();
      state.identityStep = "ask_email";
      addMessage(
        "assistant",
        "Nice to meet you, " +
        state.profile.name +
        "! 😊\n\nWhat's your email or phone number?",
        null,
        false
      );
      updateComposerState();
      return;
      /*
      if (false) addMessage(
      addMessage(
        "assistant",
        "Nice to meet you, " +
          state.profile.name +
          "! 🙌\nWhat's your email or phone number?\nI'll use it to save your progress and send over any quotes.",
        null,
        false
      );
      updateComposerState();
      return;
      */
    }

    if (state.identityStep === "ask_email") {
      if (elements.input) {
        elements.input.value = "";
      }
      addMessage("user", trimmed, null, true);

      if (!isValidEmail(trimmed) && !isValidPhone(trimmed)) {
        addMessage(
          "assistant",
          "That does not look valid. Please check and try again.",
          null,
          false
        );
        return;
      }

      if (state.requireEmailVerification && !isValidEmail(trimmed)) {
        addMessage(
          "assistant",
          "Please enter a valid email address to continue.",
          null,
          false
        );
        return;
      }

      if (isValidEmail(trimmed)) {
        state.profile.email = trimmed.toLowerCase();
        state.profile.phone = "";
        persistProfile();
        state.pendingVerificationIdentifier = state.profile.email;
        if (!(typeof VidioAuth !== "undefined" && typeof VidioAuth.requestOtp === "function")) {
          requestIdentityOtp(state.profile.email);
          updateComposerState();
          return;
        }
        state.identityStep = "ask_otp";
        addMessage(
          "assistant",
          "Got it! I've sent a 6-digit code to " +
          state.profile.email +
          ".\nEnter it here to continue. 🔐",
          null,
          false
        );
        VidioAuth.requestOtp(state.profile.email).catch(function () { });
        updateComposerState();
        return;
      }

      state.profile.phone = trimmed;
      state.profile.email = "";
      persistProfile();
      state.pendingVerificationIdentifier = state.profile.phone;
      if (!(typeof VidioAuth !== "undefined" && typeof VidioAuth.requestOtp === "function")) {
        requestIdentityOtp(state.profile.phone);
        updateComposerState();
        return;
      }
      state.identityStep = "ask_otp";
      addMessage(
        "assistant",
        "Got it! I've sent a 6-digit code to " +
        state.profile.phone +
        ".\nEnter it here to continue. 🔐",
        null,
        false
      );
      VidioAuth.requestOtp(state.profile.phone).catch(function () { });
      updateComposerState();
      return;
    }

    if (state.identityStep === "ask_email_for_meeting") {
      if (elements.input) {
        elements.input.value = "";
      }
      addMessage("user", trimmed, null, true);

      if (!isValidEmail(trimmed)) {
        addMessage(
          "assistant",
          "Please enter a valid email address so I can send your booking confirmation.",
          null,
          false
        );
        updateComposerState();
        return;
      }

      state.profile.email = trimmed.toLowerCase();
      persistProfile();
      state.identityLoading = true;
      updateComposerState();
      fetchWithRetry(
        CONFIG.apiUrl,
        {
          message: state.profile.email,
          conversation_id: state.conversationId,
          name: state.profile.name || null,
          email: state.profile.email,
          meeting_email_collection: true
        },
        function (data) {
          hideTypingIndicator();
          state.identityLoading = false;
          var reply = data.reply || data.response || data.message;
          if (reply) addMessage("assistant", reply, null, true);
          state.identityStep = null;
          setPlaceholder("Type your message…");
          updateComposerState();
        },
        function () {
          hideTypingIndicator();
          state.identityLoading = false;
          addMessage(
            "assistant",
            "Got your email! We'll send the confirmation shortly. 😊",
            null,
            true
          );
          state.identityStep = null;
          setPlaceholder("Type your message…");
          updateComposerState();
        }
      );
      return;
    }

    if (state.identityStep === "ask_otp") {
      if (elements.input) {
        elements.input.value = "";
      }
      addMessage("user", trimmed, null, true);

      if (trimmed.toLowerCase() === "resend") {
        if (verificationIdentifier && typeof VidioAuth !== "undefined" && typeof VidioAuth.requestOtp === "function") {
          VidioAuth.requestOtp(verificationIdentifier).catch(function () { });
        } else if (verificationIdentifier) {
          requestIdentityOtp(verificationIdentifier);
          return;
        }
        addMessage(
          "assistant",
          "Done! A new code has been sent to " + verificationIdentifier + ". 📲",
          null,
          false
        );
        return;
      }

      if (!/^\d{6}$/.test(trimmed)) {
        addMessage(
          "assistant",
          "That doesn't look right — please enter the 6-digit code we sent. 🔢",
          null,
          false
        );
        return;
      }

      if (typeof VidioAuth !== "undefined" && typeof VidioAuth.verifyOtp === "function") {
        state.identityLoading = true;
        updateComposerState();
        showTypingIndicator();
        state.suppressNextAuthGreeting = true;
        VidioAuth.verifyOtp(
          verificationIdentifier,
          trimmed,
          state.profile.name || null
        )
          .then(function (result) {
            hideTypingIndicator();
            state.identityLoading = false;

            if (!result || result.success !== true) {
              state.suppressNextAuthGreeting = false;
              addMessage(
                "assistant",
                "Hmm, that code didn't work. Try again or type 'resend' and I'll send a fresh one. 🔁",
                null,
                false
              );
              updateComposerState();
              return;
            }

            state.identityStep = "done";
            state.identityReady = true;
            state.profile.name = normalizeName(state.profile.name || "") || "there";
            lsSet(CONFIG.profileStorageKey, JSON.stringify(state.profile));
            lsSet("vidio_identity_verified", "1");
            addMessage(
              "assistant",
              "You're verified, " +
              state.profile.name +
              "! ✅ Now let's get back to your project — carry on! 🎬",
              null,
              false
            );
            bootstrapIdentity(false);
          })
          .catch(function () {
            state.suppressNextAuthGreeting = false;
            hideTypingIndicator();
            state.identityLoading = false;
            addMessage(
              "assistant",
              "Hmm, that code didn't work. Try again or type 'resend' and I'll send a fresh one. 🔁",
              null,
              false
            );
            updateComposerState();
          });
        return;
      }

      verifyIdentityOtp(trimmed);
      return;
    }

    if (state.identityStep === "verify_otp") {
      if (elements.input) {
        elements.input.value = "";
      }
      addMessage("user", trimmed, null, true);

      if (isOtpResend(trimmed)) {
        requestIdentityOtp(state.pendingVerificationIdentifier);
        return;
      }

      if (!/^\d{6}$/.test(trimmed)) {
        addMessage(
          "assistant",
          "Please enter the 6-digit verification code. You can also type 'resend'.",
          null,
          false
        );
        updateComposerState();
        return;
      }

      verifyIdentityOtp(trimmed);
      updateComposerState();
      return;
    }

    if (
      state.identityStep === null &&
      !state.profile.email &&
      !state.profile.phone &&
      state.hasSentFirstAnonymousMessage === false
    ) {
      if (elements.input) {
        elements.input.value = "";
      }
      addMessage("user", trimmed, null, true);
      state.hasSentFirstAnonymousMessage = true;
      state.queuedInitialMessage = trimmed;
      state.identityStep = "ask_name";
      addMessage(
        "assistant",
        "By the way — what's your name? I'd love to make this more personal for you 😊",
        null,
        false
      );
      updateComposerState();
      return;
    }

    sendMessage(trimmed);
  }

  function initFlow() {
    var hasHistory = restoreHistory();
    var hasSavedProfile = Boolean(
      state.profile && (state.profile.email || state.profile.phone)
    );
    var hasVerifiedIdentity = lsGet("vidio_identity_verified") === "1";
    var authAvailable = typeof VidioAuth !== "undefined";

    if (authAvailable && VidioAuth.isLoggedIn()) {
      var loggedInUser = VidioAuth.getUser() || {};
      state.profile.name = normalizeName(loggedInUser.name || "");
      state.profile.email = loggedInUser.email || "";
      state.profile.phone = loggedInUser.phone || "";
      state.identityStep = "done";
      state.identityReady = false;
      persistProfile();
      // AGENT FIX: guard welcome-back — fires once per session, never on subsequent messages
      if (!state.hasShownWelcomeBack) {
        state.hasShownWelcomeBack = true;
        addMessage(
          "assistant",
          "Welcome back, " +
          (state.profile.name || "there") +
          "! 👋 Glad to see you again.\n\n" +
          "I'm ready to pick up right where we left off. " +
          "What would you like to work on today?",
          null,
          false
        );
      }
      bootstrapIdentity(false);
      updateComposerState();
      return;
    }

    if (hasSavedProfile && !hasVerifiedIdentity) {
      lsRemove(CONFIG.profileStorageKey);
      lsRemove(CONFIG.historyStorageKey);
      lsRemove(CONFIG.storageKey);
      state.profile = { name: "", email: "", phone: "" };
      state.conversationId = null;
      state.messages = [];
      if (elements.msgArea) {
        elements.msgArea.innerHTML = "";
      }
      hasSavedProfile = false;
      hasHistory = false;
    }

    if (
      ((authAvailable && VidioAuth.isGuest()) || !authAvailable) &&
      hasSavedProfile &&
      hasVerifiedIdentity
    ) {
      restoreHistory();
      state.identityStep = "done";
      state.identityReady = false;
      // AGENT FIX: guard welcome-back — fires once per session, never on subsequent messages
      if (!state.hasShownWelcomeBack) {
        state.hasShownWelcomeBack = true;
        addMessage(
          "assistant",
          "Welcome back, " +
          (state.profile.name || "there") +
          "! 😊\n\n" +
          "I've got your previous conversation saved. " +
          "Shall we continue from where we left off?",
          null,
          false
        );
      }
      bootstrapIdentity(true);
      updateComposerState();
      return;
    }

    state.awaitingField = null;
    state.identityStep = "ask_name";
    state.identityReady = false;
    addMessage(
      "assistant",
      "Welcome to Ilmora Studios! 👋\n\n" +
      "I'm Vidio — your AI creative assistant here to help you find " +
      "the right video package for your brand.\n\n" +
      "To get started, may I know your name?",
      null,
      false
    );
    if (elements.input) {
      elements.input.placeholder = "Your name...";
    }
    updateComposerState();
    return;
    /*
    if (false) addMessage(
      "assistant",
      "Hey! 👋 Welcome to Ilmora Studios. I'm Vidio — here to help you find the right video package for your brand.\nWhat kind of project are you thinking about?",
      null,
      false
    );
    addMessage(
      "assistant",
      "Hey! 👋 Welcome to Ilmora Studios.\n\n" +
        "I'm Vidio, your AI creative assistant. To get started, I'll need a couple of quick details from you.",
      null,
      false
    );
    setTimeout(function () {
      addQuickReplies([
        "🎬 I need a video ad",
        "📦 View packages & pricing",
        "📞 Talk to the team",
        "❓ Something else"
      ]);
    }, 400);
    setTimeout(function () {
      addMessage(
        "assistant",
        "By the way, what's your name? I'd love to make this more personal for you.",
        null,
        false
      );
    }, 400);
    updateComposerState();
    */
  }

  function createWidget() {
    if (document.getElementById("vidio-widget")) {
      return;
    }

    injectStyles();
    restoreLocalState();

    var root = document.createElement("div");
    root.id = "vidio-widget";
    root.setAttribute("data-theme", CONFIG.theme);

    var button = document.createElement("button");
    button.id = "vidio-widget-btn";
    button.type = "button";
    button.setAttribute("aria-label", "Open " + CONFIG.agentName + " chat");
    button.setAttribute("aria-expanded", "false");
    button.innerHTML =
      '<span class="vidio-launcher-icon" aria-hidden="true">' +
      escapeHtml(CONFIG.agentAvatar) +
      "</span>";

    var badge = document.createElement("span");
    badge.id = "vidio-widget-badge";
    badge.className = "is-hidden";
    button.appendChild(badge);

    var windowEl = document.createElement("div");
    windowEl.id = "vidio-widget-window";
    windowEl.className = "is-hidden";

    var header = document.createElement("div");
    header.id = "vidio-widget-header";

    var avatar = document.createElement("div");
    avatar.className = "vidio-avatar vidio-avatar--agent";
    avatar.id = "vidio-widget-avatar";
    avatar.textContent = CONFIG.agentAvatar;

    var headerText = document.createElement("div");
    headerText.id = "vidio-widget-header-text";

    var name = document.createElement("span");
    name.className = "vidio-agent-name";
    name.textContent = CONFIG.agentName;

    var subtitle = document.createElement("span");
    subtitle.className = "vidio-agent-subtitle";
    subtitle.textContent = CONFIG.agentSubtitle;

    var status = document.createElement("span");
    status.className = "vidio-status";
    status.textContent = "Online now";

    headerText.appendChild(name);
    headerText.appendChild(subtitle);
    headerText.appendChild(status);

    var close = document.createElement("button");
    close.id = "vidio-widget-close";
    close.type = "button";
    close.setAttribute("aria-label", "Close chat");
    close.innerHTML =
      '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 6L18 18"></path><path d="M18 6L6 18"></path></svg>';

    header.appendChild(avatar);
    header.appendChild(headerText);
    header.appendChild(close);

    var messages = document.createElement("div");
    messages.id = "vidio-widget-messages";

    var inputArea = document.createElement("div");
    inputArea.id = "vidio-widget-input-area";

    var menu = document.createElement("button");
    menu.id = "vidio-widget-menu";
    menu.type = "button";
    menu.setAttribute("aria-label", "Open quick menu");
    menu.setAttribute("aria-expanded", "false");
    menu.innerHTML =
      '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 7h16"></path><path d="M4 12h16"></path><path d="M4 17h16"></path></svg>';

    var input = document.createElement("textarea");
    input.id = "vidio-widget-input";
    input.rows = 1;
    input.placeholder = "Type your message...";

    var send = document.createElement("button");
    send.id = "vidio-widget-send";
    send.type = "button";
    send.setAttribute("aria-label", "Send message");
    send.innerHTML =
      '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3.4 20.4L21 12 3.4 3.6 3.3 10l12.2 2-12.2 2z"></path></svg>';

    inputArea.appendChild(menu);
    inputArea.appendChild(input);
    inputArea.appendChild(send);

    windowEl.appendChild(header);
    windowEl.appendChild(messages);
    windowEl.appendChild(inputArea);

    root.appendChild(button);
    root.appendChild(windowEl);
    document.body.appendChild(root);

    elements.root = root;
    elements.button = button;
    elements.badge = badge;
    elements.window = windowEl;
    elements.messages = messages;
    elements.msgArea = messages;
    elements.menu = menu;
    elements.input = input;
    elements.send = send;
    elements.close = close;

    initFlow();

    button.addEventListener("click", toggleWidget);
    close.addEventListener("click", toggleWidget);
    menu.addEventListener("click", function () {
      openQuickMenu();
    });
    send.addEventListener("click", function () {
      handleSend(input.value);
    });
    input.addEventListener("keydown", function (event) {
      if (event.key === "Enter" && !event.shiftKey) {
        event.preventDefault();
        handleSend(input.value);
      }
    });
    input.addEventListener("input", function () {
      input.style.height = "40px";
      input.style.height = Math.min(input.scrollHeight, 120) + "px";
    });

    window.addEventListener("vidio:auth:login", function (event) {
      var user = event.detail || {};
      state.profile.name = normalizeName(user.name || "");
      state.profile.email = user.email || "";
      state.profile.phone = user.phone || "";
      state.identityReady = false;
      state.identityStep = "done";
      state.menuShown = false;
      state.pendingPostBootstrapMessage = user.fromWidgetFlow
        ? "Perfect, you're all set " +
        (state.profile.name || "there") +
        "! 🎉\nNow let's find the right fit for your project — carry on!"
        : null;
      state.pendingVerificationIdentifier = "";
      if (!user.fromWidgetFlow && !state.suppressNextAuthGreeting) {
        clearHistory();
        if (false) addMessage(
          "assistant",
          "Welcome, " +
          (state.profile.name || "there") +
          "! 🎬 Really glad you're here.\n" +
          "I'm Vidio — your creative guide at Ilmora Studios.\n" +
          "Whether you need a product ad, a brand film, or something completely custom, I've got you covered.\n" +
          "Tell me a bit about your project — what are you working on?",
          null,
          false
        );
        if (false) addMessage(
          "assistant",
          "Welcome, " +
          (state.profile.name || "there") +
          "! 🎬 Great to have you here.\n\n" +
          "I'm Vidio, your creative assistant at Ilmora Studios. " +
          "I can help you explore our video packages, get a quote, or schedule a call with our team.\n\n" +
          "What kind of project are you working on?",
          null,
          false
        );
        addMessage(
          "assistant",
          "Welcome, " +
          (state.profile.name || "there") +
          "! 🎬 Really glad you're here.\n" +
          "I'm Vidio — your creative guide at Ilmora Studios.\n" +
          "Whether you need a product ad, a brand film, or something completely custom, I've got you covered.\n" +
          "Tell me a bit about your project — what are you working on?",
          null,
          false
        );
      }
      showMainMenu();
      state.suppressNextAuthGreeting = false;
      persistProfile();
      bootstrapIdentity(false);
    });

    window.addEventListener("vidio:auth:guest", function () {
      if (state.isOpen) {
        addMessage(
          "assistant",
          "You can explore first. I'll guide you through the best next step.",
          null,
          false
        );
        state.menuShown = false;
        showMainMenu();
      }
    });

    window.addEventListener("vidio:auth:logout", function () {
      return;
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", createWidget);
  } else {
    createWidget();
  }
})();

