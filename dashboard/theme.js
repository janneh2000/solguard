/* SolGuard theme bootstrap.
 * Loaded synchronously in <head> to avoid FOUC.
 * - Reads localStorage('solguard-theme') if set
 * - Falls back to prefers-color-scheme
 * - Sets data-theme="light"|"dark" on <html>
 * - Wires up [data-theme-toggle] buttons after DOM ready
 * - Updates live when system pref changes (only if user hasn't picked one)
 */
(function () {
  'use strict';

  var STORAGE_KEY = 'solguard-theme';
  var root = document.documentElement;
  var mql = window.matchMedia ? window.matchMedia('(prefers-color-scheme: dark)') : null;

  function readStored() {
    try {
      var v = localStorage.getItem(STORAGE_KEY);
      return v === 'light' || v === 'dark' ? v : null;
    } catch (e) {
      return null;
    }
  }

  function writeStored(v) {
    try {
      localStorage.setItem(STORAGE_KEY, v);
    } catch (e) { /* private mode, quota */ }
  }

  function systemPref() {
    return mql && mql.matches ? 'dark' : 'light';
  }

  function effective() {
    return readStored() || systemPref();
  }

  function apply(theme) {
    root.setAttribute('data-theme', theme);
    var meta = document.querySelector('meta[name="theme-color"]');
    if (meta) {
      meta.setAttribute('content', theme === 'dark' ? '#0b0e1a' : '#ffffff');
    }
    try {
      window.dispatchEvent(new CustomEvent('solguard:themechange', { detail: { theme: theme } }));
    } catch (e) { /* old browsers */ }
  }

  /* Apply ASAP — runs before paint when this script is in <head>. */
  apply(effective());

  /* Track system preference if user has no explicit override. */
  if (mql) {
    var listener = function () {
      if (!readStored()) apply(systemPref());
    };
    if (mql.addEventListener) mql.addEventListener('change', listener);
    else if (mql.addListener) mql.addListener(listener); /* legacy Safari */
  }

  /* Wire up toggle buttons. */
  function syncButton(btn) {
    var t = effective();
    var nextLabel = t === 'dark' ? 'Switch to light mode' : 'Switch to dark mode';
    btn.setAttribute('aria-pressed', t === 'dark' ? 'true' : 'false');
    btn.setAttribute('aria-label', nextLabel);
    btn.setAttribute('title', nextLabel);
  }

  function toggle() {
    var next = effective() === 'dark' ? 'light' : 'dark';
    writeStored(next);
    apply(next);
    document.querySelectorAll('[data-theme-toggle]').forEach(syncButton);
  }

  function wire() {
    var btns = document.querySelectorAll('[data-theme-toggle]');
    btns.forEach(function (btn) {
      syncButton(btn);
      btn.addEventListener('click', function (e) {
        e.preventDefault();
        toggle();
      });
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', wire);
  } else {
    wire();
  }

  /* Re-sync any toggle buttons on system change. */
  window.addEventListener('solguard:themechange', function () {
    document.querySelectorAll('[data-theme-toggle]').forEach(syncButton);
  });

  /* Public hook in case any inline UI wants to query/set the theme. */
  window.SolguardTheme = {
    get: effective,
    set: function (t) {
      if (t === 'light' || t === 'dark') {
        writeStored(t);
        apply(t);
        document.querySelectorAll('[data-theme-toggle]').forEach(syncButton);
      }
    },
    clear: function () {
      try { localStorage.removeItem(STORAGE_KEY); } catch (e) {}
      apply(systemPref());
      document.querySelectorAll('[data-theme-toggle]').forEach(syncButton);
    }
  };
})();
