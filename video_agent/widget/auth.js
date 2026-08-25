(function () {
  "use strict";

  var STORAGE_KEY = "vidio_auth_user";

  function getStorage() {
    try {
      return window.localStorage;
    } catch (error) {
      return null;
    }
  }

  function readUser() {
    var storage = getStorage();
    if (!storage) {
      return null;
    }

    try {
      var raw = storage.getItem(STORAGE_KEY);
      return raw ? JSON.parse(raw) : null;
    } catch (error) {
      return null;
    }
  }

  function saveUser(user) {
    var storage = getStorage();
    if (!storage) {
      return;
    }

    storage.setItem(STORAGE_KEY, JSON.stringify(user));
    storage.setItem("vidio_identity_verified", "1");
  }

  function removeUser() {
    var storage = getStorage();
    if (!storage) {
      return;
    }

    storage.removeItem(STORAGE_KEY);
  }

  function readVerifiedProfile() {
    var storage = getStorage();
    if (!storage) {
      return null;
    }

    try {
      var isVerified = storage.getItem("vidio_identity_verified") === "1";
      var rawProfile = storage.getItem("vidio_user_profile");
      var profile = rawProfile ? JSON.parse(rawProfile) : null;

      if (
        !isVerified ||
        !profile ||
        (!profile.email && !profile.phone)
      ) {
        return null;
      }

      return profile;
    } catch (error) {
      return null;
    }
  }

  function syncVerifiedWidgetProfile() {
    var existingUser = readUser();
    if (existingUser) {
      return existingUser;
    }

    var profile = readVerifiedProfile();
    if (!profile) {
      return null;
    }

    var user = normalizeUser(
      {
        name: profile.name || "Member",
        email: profile.email || "",
        phone: profile.phone || ""
      },
      "password"
    );

    saveUser(user);
    return user;
  }

  function isEmail(value) {
    return String(value || "").indexOf("@") !== -1;
  }

  function getWidgetScript() {
    var current = document.currentScript;
    if (current && /auth\.js(?:\?.*)?$/i.test(current.src || "")) {
      var widgetScript = document.querySelector('script[src*="widget.js"]');
      return widgetScript || current;
    }

    return current || document.querySelector('script[src*="widget.js"]');
  }

  function parseJson(response) {
    return response
      .json()
      .catch(function () {
        return {};
      });
  }

  function normalizeUser(source, authMethod) {
    var user = {
      name: source.name || source.full_name || source.displayName || "User",
      email: source.email || "",
      phone: source.phone || "",
      authMethod: authMethod,
      token:
        source.token ||
        window.btoa(
          (source.email || source.phone || authMethod) + ":" + Date.now()
        ),
      createdAt: source.createdAt || new Date().toISOString()
    };

    return user;
  }

  function dispatch(name, detail) {
    window.dispatchEvent(
      new CustomEvent(name, {
        detail: detail || null
      })
    );
  }

  function showElement(node) {
    if (!node) {
      return;
    }

    node.style.display = node.classList.contains("vidio-nav-user")
      ? "inline-flex"
      : "inline-flex";
  }

  function hideElement(node) {
    if (!node) {
      return;
    }

    node.style.display = "none";
  }

  var VidioAuth = {
    getUser: function () {
      return readUser() || syncVerifiedWidgetProfile();
    },

    isLoggedIn: function () {
      var user = readUser();
      return Boolean(
        user &&
          (user.email || user.phone) &&
          (user.authMethod === "password" || user.authMethod === "otp")
      );
    },

    isGuest: function () {
      var user = readUser();
      return Boolean(user && user.authMethod === "guest");
    },

    getApiBase: function () {
      var script = getWidgetScript();
      var apiUrl =
        (script && script.getAttribute("data-api-url")) ||
        "http://127.0.0.1:8000/api/v1/chat";
      return apiUrl.replace(/\/api\/v1\/chat(?:\?.*)?$/i, "");
    },

    login: async function (identifier, password) {
      var apiBase = VidioAuth.getApiBase();
      var endpoint = apiBase + "/api/v1/auth/login";
      var trimmedIdentifier = String(identifier || "").trim();
      var payload = isEmail(trimmedIdentifier)
        ? { email: trimmedIdentifier, password: password }
        : { phone: trimmedIdentifier, password: password };

      try {
        var response = await fetch(endpoint, {
          method: "POST",
          headers: {
            "Content-Type": "application/json"
          },
          body: JSON.stringify(payload)
        });

        if (response.status === 404 || response.status >= 500) {
          throw new Error("MOCK_AUTH_LOGIN");
        }

        if (!response.ok) {
          return { success: false, error: "Invalid credentials" };
        }

        var data = await parseJson(response);
        if (
          !data.user ||
          (!data.user.email && !data.user.phone) ||
          !data.user.name
        ) {
          return { success: false, error: "Invalid credentials" };
        }

        var user = normalizeUser(
          {
            name: data.user.name,
            email: data.user.email,
            phone: data.user.phone,
            token: data.token
          },
          "password"
        );

        saveUser(user);
        dispatch("vidio:auth:login", user);
        return { success: true, user: user };
      } catch (error) {
        if (error && error.message !== "MOCK_AUTH_LOGIN") {
          if (String(error.message || "").indexOf("Failed to fetch") !== -1) {
            var fallbackName = isEmail(trimmedIdentifier)
              ? trimmedIdentifier.split("@")[0]
              : "User";
            var mockUser = normalizeUser(
              {
                name: fallbackName || "User",
                email: isEmail(trimmedIdentifier) ? trimmedIdentifier : "",
                phone: isEmail(trimmedIdentifier) ? "" : trimmedIdentifier
              },
              "password"
            );
            saveUser(mockUser);
            dispatch("vidio:auth:login", mockUser);
            return { success: true, user: mockUser };
          }
          return { success: false, error: "Connection failed" };
        }

        var mockName = isEmail(trimmedIdentifier)
          ? trimmedIdentifier.split("@")[0]
          : "User";
        var user = normalizeUser(
          {
            name: mockName || "User",
            email: isEmail(trimmedIdentifier) ? trimmedIdentifier : "",
            phone: isEmail(trimmedIdentifier) ? "" : trimmedIdentifier
          },
          "password"
        );
        saveUser(user);
        dispatch("vidio:auth:login", user);
        return { success: true, user: user };
      }
    },

    requestOtp: async function (identifier) {
      var apiBase = VidioAuth.getApiBase();
      var endpoint = apiBase + "/api/v1/auth/otp/request";
      var trimmedIdentifier = String(identifier || "").trim();

      try {
        var response = await fetch(endpoint, {
          method: "POST",
          headers: {
            "Content-Type": "application/json"
          },
          body: JSON.stringify({ identifier: trimmedIdentifier })
        });

        if (response.status === 404 || response.status >= 500) {
          throw new Error("MOCK_AUTH_OTP_REQUEST");
        }

        if (!response.ok) {
          var errorData = await parseJson(response);
          return {
            success: false,
            error: errorData.message || "Could not send OTP"
          };
        }

        return { success: true };
      } catch (error) {
        if (
          error &&
          error.message !== "MOCK_AUTH_OTP_REQUEST" &&
          String(error.message || "").indexOf("Failed to fetch") === -1
        ) {
          return { success: false, error: "Connection failed" };
        }

        console.log("[VidioAuth] MOCK: OTP sent to " + trimmedIdentifier);
        return { success: true };
      }
    },

    verifyOtp: async function (identifier, otp, name) {
      // ── MOCK FALLBACK — remove when backend OTP verification is live ──
      // Accepts any 6-digit number as a valid OTP
      if (/^\d{6}$/.test(otp.trim())) {
        var user = {
          name: name || (identifier.includes("@") ? identifier.split("@")[0] : "User"),
          email: identifier.includes("@") ? identifier.toLowerCase() : "",
          phone: identifier.includes("@") ? "" : identifier,
          authMethod: "otp",
          token: btoa(identifier + ":" + Date.now()),
          createdAt: new Date().toISOString()
        };
        try {
          localStorage.setItem("vidio_auth_user", JSON.stringify(user));
        } catch (_) {}
        try {
          localStorage.setItem("vidio_identity_verified", "1");
        } catch (_) {}
        window.dispatchEvent(new CustomEvent("vidio:auth:login", { detail: user }));
        console.log("[VidioAuth] MOCK: OTP verified for", identifier);
        return { success: true, user: user };
      }

      // If not 6 digits
      return { success: false, error: "Please enter a valid 6-digit code." };
    },

    continueAsGuest: function () {
      var user = {
        name: "Guest",
        email: "",
        phone: "",
        authMethod: "guest",
        token: window.btoa("guest:" + Date.now()),
        createdAt: new Date().toISOString()
      };

      saveUser(user);
      dispatch("vidio:auth:guest", user);
      VidioAuth.closeModal();
      return { success: true, user: user };
    },

    logout: function () {
      removeUser();

      try {
        window.localStorage.removeItem("vidio_identity_verified");
        window.localStorage.removeItem("vidio_user_profile");
        window.localStorage.removeItem("vidio_chat_history");
        window.localStorage.removeItem("vidio_conversation_id");
      } catch (error) {
        return;
      } finally {
        dispatch("vidio:auth:logout");
        window.location.reload();
      }
    },

    updateNavUI: function () {
      syncVerifiedWidgetProfile();
      var user = VidioAuth.getUser();
      var loggedIn = VidioAuth.isLoggedIn();
      var isGuest = VidioAuth.isGuest();
      var loggedOutEls = document.querySelectorAll(".vidio-auth-show-logged-out");
      var loggedInEls = document.querySelectorAll(".vidio-auth-show-logged-in");
      var nameEls = document.querySelectorAll(".vidio-user-display-name");
      var badgeEls = document.querySelectorAll(".vidio-user-auth-badge");

      loggedOutEls.forEach(function (el) {
        el.style.display = loggedIn || isGuest ? "none" : "";
      });

      loggedInEls.forEach(function (el) {
        if (loggedIn || isGuest) {
          el.style.display = el.classList.contains("vidio-nav-user")
            ? "inline-flex"
            : "inline-block";
        } else {
          el.style.display = "none";
        }
      });

      if (loggedIn || isGuest) {
        nameEls.forEach(function (el) {
          el.textContent = user ? user.name : "Guest";
        });

        badgeEls.forEach(function (el) {
          if (!user) {
            el.textContent = "";
            return;
          }
          if (user.authMethod === "otp") {
            el.textContent = "✦ Verified";
          } else if (user.authMethod === "guest") {
            el.textContent = "Browsing as Guest";
          } else {
            el.textContent = "✦ Member";
          }
        });
      }
    },

    showPanel: function (panelId) {
      var panels = document.querySelectorAll(".vidio-auth-panel");
      panels.forEach(function (panel) {
        panel.style.display = panel.id === panelId ? "block" : "none";
      });

      if (panelId === "vidio-panel-otp-verify") {
        var firstOtp = document.querySelector(".vidio-otp-digit");
        if (firstOtp) {
          window.setTimeout(function () {
            firstOtp.focus();
          }, 20);
        }
      }
    },

    openModal: function (mode) {
      var overlay = document.getElementById("vidio-auth-modal");
      if (!overlay) {
        return;
      }

      overlay.style.display = "flex";

      if (mode === "signin") {
        VidioAuth.showPanel("vidio-panel-signin");
      } else if (mode === "getstarted" || mode === "getstartted") {
        VidioAuth.showPanel("vidio-panel-getstarted");
      } else {
        VidioAuth.showPanel("vidio-panel-selector");
      }
    },

    closeModal: function () {
      var overlay = document.getElementById("vidio-auth-modal");
      if (overlay) {
        overlay.style.display = "none";
      }

      VidioAuth.showPanel("vidio-panel-selector");

      document.querySelectorAll("#vidio-auth-modal input").forEach(function (input) {
        input.value = "";
      });

      document.querySelectorAll(".vidio-form-error").forEach(function (errorEl) {
        errorEl.style.display = "none";
        errorEl.textContent = "";
      });

      var signinBtn = document.getElementById("vidio-signin-btn");
      var otpSendBtn = document.getElementById("vidio-otp-send-btn");
      var otpVerifyBtn = document.getElementById("vidio-otp-verify-btn");
      var otpLabel = document.getElementById("vidio-otp-sent-label");
      var resendLink = document.getElementById("vidio-otp-resend-link");

      if (signinBtn) {
        signinBtn.textContent = "Sign In";
        signinBtn.disabled = false;
      }
      if (otpSendBtn) {
        otpSendBtn.textContent = "Send One-Time Code";
        otpSendBtn.disabled = false;
      }
      if (otpVerifyBtn) {
        otpVerifyBtn.textContent = "Verify & Continue";
        otpVerifyBtn.disabled = false;
      }
      if (otpLabel) {
        otpLabel.textContent = "We sent a code to your email / phone";
      }
      if (resendLink) {
        resendLink.textContent = "Resend code";
        resendLink.dataset.locked = "false";
        resendLink.style.pointerEvents = "auto";
        resendLink.style.opacity = "1";
      }
    },

    init: function () {
      syncVerifiedWidgetProfile();
      if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", function () {
          syncVerifiedWidgetProfile();
          VidioAuth.updateNavUI();
        });
      } else {
        VidioAuth.updateNavUI();
      }
      window.addEventListener("vidio:auth:login", function () {
        VidioAuth.updateNavUI();
      });
      window.addEventListener("vidio:auth:guest", function () {
        VidioAuth.updateNavUI();
      });
      window.addEventListener("vidio:auth:logout", function () {
        VidioAuth.updateNavUI();
      });
    }
  };

  window.VidioAuth = VidioAuth;
  VidioAuth.init();
})();
