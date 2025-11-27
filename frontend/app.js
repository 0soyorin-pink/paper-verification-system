// 前端JavaScript逻辑
class PaperVerificationApp {
    constructor() {
        this.apiBase = window.location.origin;
        this.currentResults = [];
        this.totalReferences = 0;
        this.processedReferences = 0;
        this.progressInterval = null;
        this.init();
    }

    init() {
        console.log('🚀 初始化论文验证应用');
        this.bindEvents();
        this.checkBackendStatus();
        this.setupAccessibility();
    }

    bindEvents() {
        console.log('🔗 绑定事件监听器');

        // 验证按钮
        const verifyBtn = document.getElementById('verifyBtn');
        if (verifyBtn) {
            verifyBtn.addEventListener('click', () => {
                console.log('🖱️ 点击验证按钮');
                this.startVerification();
            });
        } else {
            console.error('❌ 找不到验证按钮元素');
        }

        // 清空按钮
        const clearBtn = document.getElementById('clearBtn');
        if (clearBtn) {
            clearBtn.addEventListener('click', () => {
                console.log('🖱️ 点击清空按钮');
                this.clearInput();
            });
        }

        // 文件上传
        const fileInput = document.getElementById('fileInput');
        if (fileInput) {
            fileInput.addEventListener('change', (e) => {
                console.log('📁 选择文件:', e.target.files[0]?.name);
                this.handleFileUpload(e);
            });
        }

        // 模态框关闭
        const closeModal = document.getElementById('closeModal');
        if (closeModal) {
            closeModal.addEventListener('click', () => {
                console.log('🖱️ 点击关闭模态框');
                this.hideModal();
            });
        }

        // 点击模态框背景关闭
        const detailModal = document.getElementById('detailModal');
        if (detailModal) {
            detailModal.addEventListener('click', (e) => {
                if (e.target.id === 'detailModal') {
                    console.log('🖱️ 点击模态框背景关闭');
                    this.hideModal();
                }
            });
        }

        // 加载弹窗背景点击关闭（可选）
        const loadingModal = document.getElementById('loadingModal');
        if (loadingModal) {
            loadingModal.addEventListener('click', (e) => {
                if (e.target.id === 'loadingModal') {
                    console.log('🖱️ 点击加载弹窗背景');
                    // 可以选择不允许关闭，或者允许关闭
                    // this.hideLoadingModal();
                }
            });
        }

        // 键盘事件
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                if (!document.getElementById('loadingModal').classList.contains('hidden')) {
                    console.log('ESC键: 尝试关闭加载弹窗');
                    // 可以选择不允许ESC关闭加载弹窗
                    // this.hideLoadingModal();
                } else {
                    this.hideModal();
                }
            }
        });

        console.log('✅ 所有事件监听器绑定完成');
    }

    setupAccessibility() {
        this.updateProgressBarAria(0, 100);
    }

    updateProgressBarAria(current, total) {
        const progressBar = document.querySelector('.progress-bar');
        if (progressBar) {
            const percentage = total > 0 ? Math.round((current / total) * 100) : 0;
            progressBar.setAttribute('aria-valuenow', percentage);
            progressBar.setAttribute('aria-valuetext', `进度: ${percentage}%`);
        }
    }

    announceToScreenReader(message) {
        const announcement = document.createElement('div');
        announcement.setAttribute('aria-live', 'polite');
        announcement.setAttribute('aria-atomic', 'true');
        announcement.className = 'sr-only';
        announcement.textContent = message;

        document.body.appendChild(announcement);

        setTimeout(() => {
            if (announcement.parentNode) {
                announcement.parentNode.removeChild(announcement);
            }
        }, 1000);
    }

    // 加载弹窗控制方法
    showLoadingModal(message = '正在验证中...', details = '') {
        const loadingModal = document.getElementById('loadingModal');
        const loadingProgress = document.getElementById('loadingProgress');
        const loadingDetails = document.getElementById('loadingDetails');

        if (loadingProgress) loadingProgress.textContent = message;
        if (loadingDetails) loadingDetails.textContent = details;
        if (loadingModal) {
            loadingModal.classList.remove('hidden');
            loadingModal.style.zIndex = '1000';
        }

        console.log('📱 显示加载弹窗:', message);
    }

    hideLoadingModal() {
        const loadingModal = document.getElementById('loadingModal');
        if (loadingModal) {
            loadingModal.classList.add('hidden');
        }

        // 清除进度模拟
        if (this.progressInterval) {
            clearInterval(this.progressInterval);
            this.progressInterval = null;
        }

        console.log('📱 隐藏加载弹窗');
    }

    updateLoadingProgress(message, details = '') {
        const loadingProgress = document.getElementById('loadingProgress');
        const loadingDetails = document.getElementById('loadingDetails');

        if (loadingProgress) loadingProgress.textContent = message;
        if (loadingDetails) loadingDetails.textContent = details;

        console.log('📊 更新加载进度:', message, details);
    }

    async checkBackendStatus() {
        console.log('🔍 检查后端服务状态...');
        try {
            const response = await fetch('/api/health');
            console.log('📡 健康检查响应状态:', response.status);

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            const data = await response.json();
            console.log('✅ 后端服务状态:', data);

            if (data.status === 'healthy' || data.status === 'degraded') {
                this.showNotification('后端服务连接成功', 'success');
            } else {
                this.showError('后端服务异常: ' + (data.error || '未知错误'));
            }
        } catch (error) {
            console.error('❌ 后端连接失败:', error);
            this.showNotification('无法连接到后端服务: ' + error.message, 'error');
        }
    }

    async startVerification() {
        const input = document.getElementById('referencesInput').value.trim();
        console.log('📝 输入内容:', input);

        if (!input) {
            this.showNotification('请输入参考文献内容', 'error');
            return;
        }

        // 解析输入为引用数组
        const references = this.parseReferences(input);
        console.log('📚 解析出的参考文献:', references);

        if (references.length === 0) {
            this.showNotification('未找到有效的参考文献', 'error');
            return;
        }

        if (references.length > 50) {
            if (!confirm(`检测到 ${references.length} 条参考文献，数量较多可能耗时较长，是否继续？`)) {
                return;
            }
        }

        this.setLoadingState(true);
        this.showProgress();
        this.resetResults();

        // 显示加载弹窗
        this.showLoadingModal(
            '开始验证参考文献...',
            `共 ${references.length} 条文献需要验证`
        );

        try {
            console.log('🚀 开始批量验证...');

            // 更新进度信息
            this.updateLoadingProgress(
                '正在连接验证服务...',
                '初始化多智能体验证系统'
            );

            // 开始模拟进度
            this.startProgressSimulation(references.length);

            const result = await this.verifyBatch(references);
            console.log('✅ 批量验证完成:', result);

            // 验证完成，隐藏弹窗
            this.hideLoadingModal();
            this.displayResults(result);

        } catch (error) {
            console.error('❌ 验证过程出错:', error);
            // 出错时也要隐藏弹窗
            this.hideLoadingModal();
            this.showNotification('验证过程出错: ' + error.message, 'error');
        } finally {
            this.setLoadingState(false);
        }
    }

    parseReferences(input) {
        // 按行分割，过滤空行和注释
        return input.split('\n')
            .map(line => line.trim())
            .filter(line => line && !line.startsWith('//') && !line.startsWith('#'));
    }

    async verifyBatch(references) {
        console.log('📤 发送批量验证请求到 /api/verify-batch');
        console.log('📦 请求数据:', { references });

        this.totalReferences = references.length;
        this.processedReferences = 0;

        try {
            const response = await fetch('/api/verify-batch', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ references })
            });

            console.log('📡 API 响应状态:', response.status, response.statusText);

            if (!response.ok) {
                let errorMessage = `HTTP ${response.status}`;
                try {
                    const errorData = await response.json();
                    errorMessage = errorData.error || errorMessage;
                    console.error('❌ API 错误响应:', errorData);
                } catch (e) {
                    errorMessage = response.statusText || errorMessage;
                    console.error('❌ API 响应解析失败:', e);
                }
                throw new Error(errorMessage);
            }

            const data = await response.json();
            console.log('📥 API 成功响应:', data);
            return data;

        } catch (error) {
            console.error('❌ 网络请求失败:', error);
            throw error;
        }
    }

    // 进度模拟方法
    startProgressSimulation(total) {
        let current = 0;
        const maxProgress = 90; // 最大模拟到90%，等待真实结果

        // 清除之前的间隔
        if (this.progressInterval) {
            clearInterval(this.progressInterval);
        }

        this.progressInterval = setInterval(() => {
            if (current < maxProgress) {
                current += Math.floor(Math.random() * 5) + 1;
                if (current > maxProgress) current = maxProgress;

                const progressMessage = this.getRandomProgressMessage();
                this.updateProgress(current, 100, progressMessage);
                this.updateLoadingProgress(
                    progressMessage,
                    `进度: ${current}% - 正在处理第 ${Math.floor(current / 100 * total)} 条文献`
                );
            }
        }, 800);
    }

    getRandomProgressMessage() {
        const messages = [
            '正在解析文献格式...',
            '查询学术数据库...',
            '验证作者信息...',
            '检查期刊真实性...',
            '分析引用关系...',
            '交叉验证数据源...',
            '生成验证报告...',
            '智能分析文献内容...',
            '比对权威数据源...',
            '评估文献可信度...'
        ];
        return messages[Math.floor(Math.random() * messages.length)];
    }

    updateProgress(current, total, message) {
        const progressFill = document.getElementById('progressFill');
        const progressText = document.getElementById('progressText');
        const progressCount = document.getElementById('progressCount');

        const percentage = total > 0 ? (current / total) * 100 : 0;
        if (progressFill) progressFill.style.width = `${percentage}%`;
        if (progressText) progressText.textContent = message || `处理中...`;
        if (progressCount) progressCount.textContent = `${current}/${total}`;

        this.updateProgressBarAria(current, total);

        if (current > 0 && total > 0) {
            this.announceToScreenReader(`进度: ${current} 条中的第 ${total} 条，${message}`);
        }
    }

    displayResults(data) {
        console.log('📊 显示验证结果:', data);

        if (!data.success) {
            this.showNotification('验证失败: ' + data.error, 'error');
            return;
        }

        this.currentResults = data.results;
        this.updateSummary(data.results);
        this.renderResultsTable(data.results);
        this.showResults();

        // 更新最终进度为100%
        this.updateProgress(100, 100, '验证完成');

        const realCount = data.results.filter(r => r.is_real === true).length;
        const totalCount = data.results.length;
        this.announceToScreenReader(`验证完成: 总共 ${totalCount} 条文献，其中 ${realCount} 条验证为真实`);

        this.showNotification(`验证完成！共处理 ${totalCount} 条文献`, 'success');
    }

    updateSummary(results) {
        const realCount = results.filter(r => r.is_real === true).length;
        const questionableCount = results.filter(r =>
            r.is_real === false && r.confidence > 0.3
        ).length;
        const fakeCount = results.filter(r =>
            r.is_real === false && r.confidence <= 0.3
        ).length;

        document.getElementById('realCount').textContent = realCount;
        document.getElementById('questionableCount').textContent = questionableCount;
        document.getElementById('fakeCount').textContent = fakeCount;
        document.getElementById('totalCount').textContent = results.length;

        console.log('📈 结果统计 - 真实:', realCount, '存疑:', questionableCount, '未验证:', fakeCount, '总计:', results.length);
    }

    renderResultsTable(results) {
        const tbody = document.getElementById('resultsBody');
        tbody.innerHTML = '';

        if (results.length === 0) {
            const emptyRow = document.createElement('tr');
            emptyRow.innerHTML = '<td colspan="6" style="text-align: center; color: #999;">暂无验证结果</td>';
            tbody.appendChild(emptyRow);
            return;
        }

        results.forEach((result, index) => {
            const row = this.createResultRow(result, index);
            tbody.appendChild(row);
        });

        console.log('📋 渲染结果表格，共', results.length, '行');
    }

    createResultRow(result, index) {
        const row = document.createElement('tr');

        // 状态列
        const statusCell = document.createElement('td');
        statusCell.appendChild(this.createStatusBadge(result));

        // 标题列
        const titleCell = document.createElement('td');
        const titleText = result.title || result.reference.substring(0, 50) + (result.reference.length > 50 ? '...' : '');
        titleCell.textContent = titleText;
        titleCell.setAttribute('title', result.title || result.reference);

        // 类型列
        const typeCell = document.createElement('td');
        typeCell.textContent = this.formatType(result.type);

        // 置信度列
        const confidenceCell = document.createElement('td');
        confidenceCell.appendChild(this.createConfidenceBar(result.confidence));

        // 来源列
        const sourceCell = document.createElement('td');
        sourceCell.textContent = result.source || '未知';

        // 操作列
        const actionCell = document.createElement('td');
        actionCell.appendChild(this.createActionButtons(result, index));

        row.appendChild(statusCell);
        row.appendChild(titleCell);
        row.appendChild(typeCell);
        row.appendChild(confidenceCell);
        row.appendChild(sourceCell);
        row.appendChild(actionCell);

        return row;
    }

    createStatusBadge(result) {
        const badge = document.createElement('span');
        badge.className = 'status-badge ';

        if (result.error) {
            badge.textContent = '错误';
            badge.className += 'status-unknown';
        } else if (result.is_real === true) {
            badge.textContent = '真实';
            badge.className += 'status-real';
        } else if (result.confidence > 0.3) {
            badge.textContent = '存疑';
            badge.className += 'status-questionable';
        } else {
            badge.textContent = '未验证';
            badge.className += 'status-fake';
        }

        return badge;
    }

    createConfidenceBar(confidence) {
        const container = document.createElement('div');

        const bar = document.createElement('div');
        bar.className = 'confidence-bar';

        const fill = document.createElement('div');
        fill.className = 'confidence-fill';

        if (confidence >= 0.7) {
            fill.className += ' confidence-high';
        } else if (confidence >= 0.4) {
            fill.className += ' confidence-medium';
        } else {
            fill.className += ' confidence-low';
        }

        fill.style.width = `${(confidence || 0) * 100}%`;
        bar.appendChild(fill);
        container.appendChild(bar);

        const text = document.createElement('div');
        text.textContent = `${((confidence || 0) * 100).toFixed(1)}%`;
        text.className = 'confidence-text';
        container.appendChild(text);

        return container;
    }

    createActionButtons(result, index) {
        const container = document.createElement('div');
        container.className = 'action-buttons';

        const detailBtn = document.createElement('button');
        detailBtn.textContent = '详情';
        detailBtn.className = 'btn-secondary btn-small detail-btn';
        detailBtn.setAttribute('aria-label', `查看 ${result.title || '文献'} 的详细验证信息`);
        detailBtn.addEventListener('click', () => {
            console.log('🔍 查看详情:', result);
            this.showDetailModal(result);
        });

        container.appendChild(detailBtn);

        return container;
    }

    showDetailModal(result) {
        const modalContent = document.getElementById('modalContent');
        modalContent.innerHTML = this.generateDetailContent(result);

        const modal = document.getElementById('detailModal');
        modal.classList.remove('hidden');

        const closeBtn = document.getElementById('closeModal');
        closeBtn.focus();

        this.announceToScreenReader('打开详细验证信息对话框');
    }

    generateDetailContent(result) {
        console.log('🔍 详细模态框接收的数据:', result);

        // 正确访问嵌套字段
        const rawData = result.details?.raw_data || {};
        const parsedData = result.details?.parsed_data || {};

        console.log('🔗 raw_data 实际内容:', rawData);
        console.log('📝 parsed_data 实际内容:', parsedData);

        // 从正确的位置获取字段
        const paperLink = rawData.link || result.link;
        const paperYear = parsedData.year || rawData.published_date || result.published_date;
        const paperAuthors = rawData.authors || result.authors;

        console.log('✅ 链接:', paperLink);
        console.log('✅ 年份:', paperYear);
        console.log('✅ 作者:', paperAuthors);
        console.log('✅ 直接字段 - link:', result.link, 'published_date:', result.published_date);

        // 构建来源链接HTML
        let sourceLinkHTML = '';
        if (paperLink) {
            sourceLinkHTML = `
            <div class="detail-item">
                <div class="detail-label">来源链接</div>
                <div class="detail-value">
                    <a href="${this.escapeHtml(paperLink)}" target="_blank" rel="noopener noreferrer" class="source-link">
                        ${this.escapeHtml(paperLink)}
                    </a>
                </div>
            </div>
        `;
        } else {
            sourceLinkHTML = `
            <div class="detail-item">
                <div class="detail-label">来源链接</div>
                <div class="detail-value" style="color: #999;">暂无可用链接</div>
            </div>
        `;
        }

        return `
        <div class="detail-item">
            <div class="detail-label">原始引用</div>
            <div class="detail-value">${this.escapeHtml(result.reference)}</div>
        </div>
        
        <div class="detail-item">
            <div class="detail-label">解析类型</div>
            <div class="detail-value">${this.formatType(result.type)}</div>
        </div>
        
        <div class="detail-item">
            <div class="detail-label">验证状态</div>
            <div class="detail-value">${this.getStatusText(result)}</div>
        </div>
        
        <div class="detail-item">
            <div class="detail-label">置信度</div>
            <div class="detail-value">${((result.confidence || 0) * 100).toFixed(1)}%</div>
        </div>
        
        <div class="detail-item">
            <div class="detail-label">数据来源</div>
            <div class="detail-value">${result.source || '未知'}</div>
        </div>
        
        ${sourceLinkHTML}
        
        ${paperYear ? `
        <div class="detail-item">
            <div class="detail-label">发表年份</div>
            <div class="detail-value">${this.escapeHtml(paperYear)}</div>
        </div>
        ` : ''}
        
        ${result.title ? `
        <div class="detail-item">
            <div class="detail-label">识别标题</div>
            <div class="detail-value">${this.escapeHtml(result.title)}</div>
        </div>
        ` : ''}
        
        ${paperAuthors ? `
        <div class="detail-item">
            <div class="detail-label">作者信息</div>
            <div class="detail-value">${this.escapeHtml(paperAuthors)}</div>
        </div>
        ` : ''}
        
        ${result.reason ? `
        <div class="detail-item">
            <div class="detail-label">判断理由</div>
            <div class="detail-value">${this.escapeHtml(result.reason)}</div>
        </div>
        ` : ''}
    `;
    }

    getStatusText(result) {
        if (result.error) return '❌ 验证错误';
        if (result.is_real === true) return '✅ 真实存在';
        if (result.confidence > 0.3) return '⚠️ 可能存疑';
        return '❌ 未验证通过';
    }

    formatType(type) {
        const typeMap = {
            'paper': '论文',
            'patent': '专利',
            'unknown': '未知'
        };
        return typeMap[type] || type;
    }

    escapeHtml(unsafe) {
        if (!unsafe) return '';
        return unsafe
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }

    hideModal() {
        const modal = document.getElementById('detailModal');
        modal.classList.add('hidden');

        const activeElement = document.activeElement;
        if (activeElement && activeElement.classList.contains('detail-btn')) {
            activeElement.focus();
        }

        this.announceToScreenReader('关闭详细验证信息对话框');
    }

    clearInput() {
        document.getElementById('referencesInput').value = '';
        console.log('🗑️ 清空输入框');
    }

    async handleFileUpload(event) {
        const file = event.target.files[0];
        if (!file) return;

        console.log('📁 处理文件上传:', file.name);

        const reader = new FileReader();
        reader.onload = (e) => {
            document.getElementById('referencesInput').value = e.target.result;
            this.showNotification('文件上传成功', 'success');
            console.log('✅ 文件读取成功');
        };
        reader.onerror = () => {
            this.showNotification('文件读取失败', 'error');
            console.error('❌ 文件读取失败');
        };
        reader.readAsText(file);

        event.target.value = '';
    }

    setLoadingState(loading) {
        const verifyBtn = document.getElementById('verifyBtn');
        if (verifyBtn) {
            verifyBtn.disabled = loading;
            verifyBtn.textContent = loading ? '验证中...' : '开始验证';
        }

        if (loading) {
            document.body.classList.add('loading');
            console.log('⏳ 设置加载状态: 开启');
        } else {
            document.body.classList.remove('loading');
            console.log('⏳ 设置加载状态: 关闭');
        }
    }

    showProgress() {
        const progressSection = document.getElementById('progressSection');
        if (progressSection) {
            progressSection.classList.remove('hidden');
        }
        this.updateProgress(0, 1, '准备开始验证...');
        console.log('📊 显示进度条');
    }

    showResults() {
        const resultsSection = document.getElementById('resultsSection');
        if (resultsSection) {
            resultsSection.classList.remove('hidden');
        }
        console.log('📋 显示结果区域');
    }

    resetResults() {
        this.currentResults = [];
        const resultsBody = document.getElementById('resultsBody');
        if (resultsBody) {
            resultsBody.innerHTML = '';
        }
        document.getElementById('realCount').textContent = '0';
        document.getElementById('questionableCount').textContent = '0';
        document.getElementById('fakeCount').textContent = '0';
        document.getElementById('totalCount').textContent = '0';
        console.log('🔄 重置结果');
    }

    showNotification(message, type = 'info') {
        console.log(`${type.toUpperCase()}: ${message}`);

        // 创建通知元素
        const notification = document.createElement('div');
        notification.className = `notification ${type}`;
        notification.textContent = message;

        document.body.appendChild(notification);

        // 3秒后自动移除
        setTimeout(() => {
            if (notification.parentNode) {
                notification.parentNode.removeChild(notification);
            }
        }, 3000);

        if (type === 'error') {
            console.error('❌', message);
        } else if (type === 'success') {
            console.log('✅', message);
        }
    }
}

// 页面加载完成后初始化应用
document.addEventListener('DOMContentLoaded', () => {
    console.log('📄 DOM 加载完成，初始化应用');
    new PaperVerificationApp();
});