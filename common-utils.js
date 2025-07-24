/**
 * ベテランAI Ver.003 - 共通ユーティリティライブラリ
 * セキュリティ、パフォーマンス、アクセシビリティを統合
 */

// ========== セキュリティユーティリティ ==========
class SecurityUtils {
    static DANGEROUS_PATTERNS = [
        /<script[^>]*>.*?<\/script>/gi,
        /javascript:/gi,
        /on\w+\s*=/gi,
        /<iframe[^>]*>.*?<\/iframe>/gi,
        /data:\s*text\/html/gi,
        /vbscript:/gi
    ];

    static validateInput(input, maxLength = 1000, allowHtml = false) {
        if (!input || typeof input !== 'string') {
            throw new ValidationError('無効な入力です');
        }

        const trimmed = input.trim();
        
        if (trimmed.length === 0) {
            throw new ValidationError('入力が空です');
        }
        
        if (trimmed.length > maxLength) {
            throw new ValidationError(`入力は${maxLength}文字以内にしてください`);
        }

        if (!allowHtml) {
            for (const pattern of this.DANGEROUS_PATTERNS) {
                if (pattern.test(trimmed)) {
                    throw new SecurityError('不正な内容が含まれています');
                }
            }
        }

        return trimmed;
    }

    static sanitizeHtml(input) {
        const div = document.createElement('div');
        div.textContent = input;
        return div.innerHTML;
    }

    static generateNonce() {
        const array = new Uint8Array(16);
        crypto.getRandomValues(array);
        return Array.from(array, byte => byte.toString(16).padStart(2, '0')).join('');
    }
}

// ========== トークン管理システム ==========
class TokenManager {
    static TOKEN_KEY = 'veteran_ai_token';
    static cleanupTimer = null;

    static setToken(token, expiresIn = 3600) {
        try {
            const expiry = Date.now() + (expiresIn * 1000);
            const tokenData = {
                token: token,
                expiry: expiry,
                created: Date.now(),
                nonce: SecurityUtils.generateNonce()
            };

            sessionStorage.setItem(this.TOKEN_KEY, JSON.stringify(tokenData));
            this.scheduleCleanup(expiresIn * 1000);
            
            return true;
        } catch (error) {
            console.error('Failed to store token:', error);
            return false;
        }
    }

    static getToken() {
        try {
            const stored = sessionStorage.getItem(this.TOKEN_KEY) || 
                          localStorage.getItem(this.TOKEN_KEY);
            if (!stored) return null;

            const tokenData = JSON.parse(stored);

            if (Date.now() > tokenData.expiry) {
                this.clearToken();
                return null;
            }

            if (!this.isValidJWT(tokenData.token)) {
                this.clearToken();
                return null;
            }

            return tokenData.token;
        } catch (error) {
            console.error('Failed to retrieve token:', error);
            this.clearToken();
            return null;
        }
    }

    static clearToken() {
        sessionStorage.removeItem(this.TOKEN_KEY);
        localStorage.removeItem(this.TOKEN_KEY);
        
        if (this.cleanupTimer) {
            clearTimeout(this.cleanupTimer);
            this.cleanupTimer = null;
        }
    }

    static isValidJWT(token) {
        if (!token || typeof token !== 'string') return false;

        const parts = token.split('.');
        if (parts.length !== 3) return false;

        try {
            const payload = JSON.parse(atob(parts[1]));
            return payload.exp && payload.iat && payload.exp * 1000 > Date.now();
        } catch {
            return false;
        }
    }

    static scheduleCleanup(delay) {
        if (this.cleanupTimer) {
            clearTimeout(this.cleanupTimer);
        }

        this.cleanupTimer = setTimeout(() => {
            if (!this.getToken()) {
                NotificationManager.error('セッションが期限切れです', {
                    action: () => window.location.href = '/frontend_auth.html'
                });
            }
        }, delay);
    }

    static getTimeToExpiry() {
        try {
            const stored = sessionStorage.getItem(this.TOKEN_KEY) || 
                          localStorage.getItem(this.TOKEN_KEY);
            if (!stored) return 0;

            const tokenData = JSON.parse(stored);
            return Math.max(0, tokenData.expiry - Date.now());
        } catch {
            return 0;
        }
    }
}

// ========== 通知管理システム ==========
class NotificationManager {
    static container = null;
    static notifications = new Map();

    static init() {
        if (!this.container) {
            this.container = document.createElement('div');
            this.container.id = 'notification-container';
            this.container.className = 'notification-container';
            this.container.setAttribute('aria-live', 'polite');
            document.body.appendChild(this.container);
        }
    }

    static show(message, type = 'info', options = {}) {
        this.init();
        
        const id = SecurityUtils.generateNonce();
        const notification = this.createNotification(id, message, type, options);
        
        this.container.appendChild(notification);
        this.notifications.set(id, notification);

        // アニメーション
        requestAnimationFrame(() => {
            notification.classList.add('show');
        });

        // 自動削除
        const duration = options.duration || 5000;
        setTimeout(() => this.remove(id), duration);

        return id;
    }

    static createNotification(id, message, type, options) {
        const notification = document.createElement('div');
        notification.className = `notification notification-${type}`;
        notification.setAttribute('role', 'alert');
        notification.dataset.id = id;

        const content = document.createElement('div');
        content.className = 'notification-content';
        content.textContent = message;

        const closeBtn = document.createElement('button');
        closeBtn.className = 'notification-close';
        closeBtn.textContent = '×';
        closeBtn.setAttribute('aria-label', '通知を閉じる');
        closeBtn.addEventListener('click', () => this.remove(id));

        notification.appendChild(content);
        notification.appendChild(closeBtn);

        if (options.action) {
            const actionBtn = document.createElement('button');
            actionBtn.className = 'notification-action';
            actionBtn.textContent = options.actionText || '実行';
            actionBtn.addEventListener('click', () => {
                options.action();
                this.remove(id);
            });
            notification.appendChild(actionBtn);
        }

        return notification;
    }

    static remove(id) {
        const notification = this.notifications.get(id);
        if (notification) {
            notification.classList.add('hide');
            setTimeout(() => {
                if (notification.parentNode) {
                    notification.parentNode.removeChild(notification);
                }
                this.notifications.delete(id);
            }, 300);
        }
    }

    static success(message, options = {}) {
        return this.show(message, 'success', options);
    }

    static error(message, options = {}) {
        return this.show(message, 'error', options);
    }

    static warning(message, options = {}) {
        return this.show(message, 'warning', options);
    }

    static info(message, options = {}) {
        return this.show(message, 'info', options);
    }
}

// ========== API クライアント ==========
class ApiClient {
    static BASE_URL = '/api';
    static DEFAULT_TIMEOUT = 30000;

    static async request(endpoint, options = {}) {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 
                                    options.timeout || this.DEFAULT_TIMEOUT);

        try {
            const token = TokenManager.getToken();
            const config = {
                method: 'GET',
                headers: {
                    'Content-Type': 'application/json',
                    ...(token && { 'Authorization': `Bearer ${token}` }),
                    ...options.headers
                },
                signal: controller.signal,
                ...options
            };

            const response = await fetch(`${this.BASE_URL}${endpoint}`, config);
            clearTimeout(timeoutId);

            if (!response.ok) {
                const errorData = await response.json();
                throw new ApiError(
                    this.getErrorMessage(response.status, errorData.error),
                    response.status
                );
            }

            return await response.json();
        } catch (error) {
            clearTimeout(timeoutId);
            
            if (error.name === 'AbortError') {
                throw new TimeoutError('リクエストがタイムアウトしました');
            }
            
            throw error;
        }
    }

    static getErrorMessage(status, message) {
        const messages = {
            400: '入力内容に問題があります',
            401: 'ログインが必要です',
            403: 'アクセス権限がありません',
            404: 'リソースが見つかりません',
            429: 'リクエストが多すぎます。しばらく待ってから再試行してください',
            500: 'サーバーエラーが発生しました',
            503: 'サービスが一時的に利用できません'
        };

        return messages[status] || message || '不明なエラーが発生しました';
    }

    static get(endpoint, options = {}) {
        return this.request(endpoint, { method: 'GET', ...options });
    }

    static post(endpoint, data, options = {}) {
        return this.request(endpoint, {
            method: 'POST',
            body: JSON.stringify(data),
            ...options
        });
    }

    static patch(endpoint, data, options = {}) {
        return this.request(endpoint, {
            method: 'PATCH',
            body: JSON.stringify(data),
            ...options
        });
    }

    static delete(endpoint, options = {}) {
        return this.request(endpoint, { method: 'DELETE', ...options });
    }
}

// ========== DOM ヘルパー ==========
class DOMHelper {
    static createElement(tag, attributes = {}, textContent = '') {
        const element = document.createElement(tag);
        
        Object.entries(attributes).forEach(([key, value]) => {
            if (key === 'className') {
                element.className = value;
            } else if (key.startsWith('aria-') || key.startsWith('data-') || 
                      ['id', 'role', 'tabindex', 'title'].includes(key)) {
                element.setAttribute(key, value);
            } else {
                element[key] = value;
            }
        });

        if (textContent) {
            element.textContent = textContent;
        }

        return element;
    }

    static batchUpdate(container, updateFn) {
        const fragment = document.createDocumentFragment();
        const tempContainer = container.cloneNode(false);
        
        updateFn(tempContainer);
        
        while (tempContainer.firstChild) {
            fragment.appendChild(tempContainer.firstChild);
        }
        
        container.innerHTML = '';
        container.appendChild(fragment);
    }

    static debounce(func, wait) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    }

    static throttle(func, limit) {
        let inThrottle;
        return function executedFunction(...args) {
            if (!inThrottle) {
                func.apply(this, args);
                inThrottle = true;
                setTimeout(() => inThrottle = false, limit);
            }
        };
    }
}

// ========== カスタムエラークラス ==========
class ValidationError extends Error {
    constructor(message) {
        super(message);
        this.name = 'ValidationError';
    }
}

class SecurityError extends Error {
    constructor(message) {
        super(message);
        this.name = 'SecurityError';
    }
}

class ApiError extends Error {
    constructor(message, status) {
        super(message);
        this.name = 'ApiError';
        this.status = status;
    }
}

class TimeoutError extends Error {
    constructor(message) {
        super(message);
        this.name = 'TimeoutError';
    }
}

// ========== キーボードナビゲーション ==========
class KeyboardNavigation {
    static focusableSelectors = [
        'a[href]',
        'button:not([disabled])',
        'input:not([disabled])',
        'select:not([disabled])',
        'textarea:not([disabled])',
        '[tabindex]:not([tabindex="-1"])'
    ].join(', ');

    static init() {
        document.addEventListener('keydown', this.handleGlobalKeydown.bind(this));
    }

    static handleGlobalKeydown(e) {
        switch(e.key) {
            case 'Escape':
                this.closeModals();
                break;
            case 'Tab':
                this.handleTabNavigation(e);
                break;
        }
    }

    static closeModals() {
        document.querySelectorAll('.modal[style*="block"]').forEach(modal => {
            const closeBtn = modal.querySelector('.close-btn, [data-close]');
            if (closeBtn) {
                closeBtn.click();
            }
        });
    }

    static handleTabNavigation(e) {
        const modal = document.querySelector('.modal[style*="block"]');
        if (modal) {
            this.trapFocus(e, modal);
        }
    }

    static trapFocus(e, container) {
        const focusableElements = container.querySelectorAll(this.focusableSelectors);
        const firstElement = focusableElements[0];
        const lastElement = focusableElements[focusableElements.length - 1];

        if (e.shiftKey) {
            if (document.activeElement === firstElement) {
                e.preventDefault();
                lastElement.focus();
            }
        } else {
            if (document.activeElement === lastElement) {
                e.preventDefault();
                firstElement.focus();
            }
        }
    }
}

// ========== パフォーマンス監視 ==========
class PerformanceMonitor {
    static measurements = new Map();

    static start(name) {
        this.measurements.set(name, performance.now());
    }

    static end(name) {
        const startTime = this.measurements.get(name);
        if (startTime) {
            const duration = performance.now() - startTime;
            console.log(`⏱️ ${name}: ${duration.toFixed(2)}ms`);
            this.measurements.delete(name);
            return duration;
        }
    }

    static measure(name, fn) {
        this.start(name);
        const result = fn();
        this.end(name);
        return result;
    }
}

// ========== 初期化 ==========
document.addEventListener('DOMContentLoaded', () => {
    KeyboardNavigation.init();
    NotificationManager.init();
});

// グローバルに公開する従来の関数（後方互換性）
window.getAuthToken = () => TokenManager.getToken();
window.escapeHtml = (text) => SecurityUtils.sanitizeHtml(text);