package com.namvibe.app;

import android.util.Log;
import android.webkit.CookieManager;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.ValueCallback;
import com.getcapacitor.BridgeActivity;

public class MainActivity extends BridgeActivity {
    private static final String TAG = "NamVibeWebView";
    private static final String APP_HOST = "http://192.168.179.30:5000";

    @Override
    public void onStart() {
        super.onStart();
        WebView webView = getBridge().getWebView();
        if (webView != null) {
            WebSettings settings = webView.getSettings();
            settings.setMediaPlaybackRequiresUserGesture(false);
            settings.setAllowFileAccess(true);
            settings.setAllowContentAccess(true);
            settings.setJavaScriptEnabled(true);
            settings.setDomStorageEnabled(true);

            CookieManager cookieManager = CookieManager.getInstance();
            cookieManager.setAcceptCookie(true);
            cookieManager.setAcceptThirdPartyCookies(webView, true);
            cookieManager.flush();

            Log.d(TAG, "CookieManager initialized: acceptCookie=" + cookieManager.acceptCookie());
        }
    }

    @Override
    public void onResume() {
        super.onResume();
        logDebugInfo();
    }

    private void logDebugInfo() {
        try {
            WebView webView = getBridge().getWebView();
            if (webView == null) {
                Log.w(TAG, "WebView is null – cannot log debug info");
                return;
            }
            webView.evaluateJavascript("(function(){ return window.location.href; })();", new ValueCallback<String>() {
                @Override
                public void onReceiveValue(String url) {
                    Log.d(TAG, "Current URL: " + url);
                }
            });

            CookieManager cookieManager = CookieManager.getInstance();
            String cookies = cookieManager.getCookie(APP_HOST);
            Log.d(TAG, "Cookies for " + APP_HOST + ": " + (cookies != null ? cookies.replaceAll("session=([^;]+)", "session=***") : "none"));

            webView.evaluateJavascript(
                "(function() {" +
                "  fetch('/auth/debug-session', { credentials: 'include' })" +
                "    .then(r => r.json())" +
                "    .then(d => console.log('NamVibeDebug:', JSON.stringify(d)))" +
                "    .catch(e => console.log('NamVibeDebug error:', e.message));" +
                "})();",
                null
            );
            Log.d(TAG, "Debug info requested via /auth/debug-session");
        } catch (Exception e) {
            Log.e(TAG, "Error in logDebugInfo", e);
        }
    }
}
