        // Shared right-side workbench for user-facing artifacts. Creation
        // cards and confirmation cards share this surface with the trace view.
        const workbenchState = {
            activeView: 'trace',
            activeCardId: null,
            cards: new Map(),
            open: false,
        };

        function setWorkbenchView(view) {
            const nextView = view === 'creation' ? 'creation' : 'trace';
            workbenchState.activeView = nextView;
            const traceView = document.getElementById('trace-workbench-view');
            const creationView = document.getElementById('creation-workbench-view');
            const traceTab = document.getElementById('workbench-tab-trace');
            const creationTab = document.getElementById('workbench-tab-creation');
            if (traceView) traceView.hidden = nextView !== 'trace';
            if (creationView) creationView.hidden = nextView !== 'creation';
            traceTab?.classList.toggle('active', nextView === 'trace');
            traceTab?.setAttribute('aria-selected', String(nextView === 'trace'));
            creationTab?.classList.toggle('active', nextView === 'creation');
            creationTab?.setAttribute('aria-selected', String(nextView === 'creation'));
            document.querySelector('.right-panel')?.classList.toggle('workbench-creation-active', nextView === 'creation');
        }

        function openAgentWorkbench(view = 'trace') {
            const panel = document.querySelector('.right-panel');
            if (!panel) return;
            const wasOpen = workbenchState.open;
            workbenchState.open = true;
            document.body.classList.add('workbench-open');
            document.body.classList.remove('trace-collapsed');
            if (!wasOpen) document.body.classList.remove('trace-expanded');
            panel.classList.remove('trace-collapsed');
            setWorkbenchView(view);
        }

        function closeAgentWorkbench() {
            const panel = document.querySelector('.right-panel');
            workbenchState.open = false;
            if (typeof traceState !== 'undefined') traceState.expanded = false;
            document.body.classList.remove('workbench-open', 'trace-collapsed', 'trace-expanded');
            panel?.classList.remove('trace-collapsed');
        }

        function openCreationWorkbench(card = null) {
            if (card) {
                workbenchState.cards.set(String(card.id), card);
                workbenchState.activeCardId = String(card.id);
            }
            openAgentWorkbench('creation');
            const host = document.getElementById('creation-workbench-host');
            const confirmationHost = document.getElementById('confirmation-workbench-host');
            if (host) host.hidden = false;
            if (confirmationHost) confirmationHost.hidden = true;
            const title = document.getElementById('workbenchCreationTitle');
            const subtitle = document.getElementById('workbenchCreationSubtitle');
            if (title) title.textContent = card?.title || '广告创建参数';
            if (subtitle) subtitle.textContent = card
                ? '在右侧完成参数、联动校验和预览；提交前仍需要你的明确确认。'
                : '选择一张创建卡片继续填写，或从聊天记录重新打开。';
            updateCreationWorkbenchCount();
        }

        function closeCreationWorkbench() {
            const confirmationHost = document.getElementById('confirmation-workbench-host');
            if (confirmationHost) confirmationHost.hidden = true;
            closeAgentWorkbench();
        }

        function openConfirmationWorkbench() {
            openAgentWorkbench('creation');
            const host = document.getElementById('creation-workbench-host');
            const confirmationHost = document.getElementById('confirmation-workbench-host');
            if (host) host.hidden = true;
            if (confirmationHost) confirmationHost.hidden = false;
            const title = document.getElementById('workbenchCreationTitle');
            const subtitle = document.getElementById('workbenchCreationSubtitle');
            if (title) title.textContent = '提交前确认';
            if (subtitle) subtitle.textContent = '请检查账户、层级、预算、定向和素材；确认后才会继续执行。';
        }

        function updateCreationWorkbenchCount() {
            const count = document.getElementById('workbenchCreationCount');
            if (!count) return;
            const size = workbenchState.cards.size;
            count.textContent = size ? `${size} 张` : '';
            count.hidden = !size;
        }

        function renderCreationCardInWorkbench(card, { open = true } = {}) {
            if (!card?.id) return null;
            workbenchState.cards.set(String(card.id), card);
            workbenchState.activeCardId = String(card.id);
            const host = document.getElementById('creation-workbench-host');
            if (!host) return null;
            host.hidden = false;
            const wrapper = renderCreationCard(card);
            host.replaceChildren(wrapper);
            if (open) openCreationWorkbench(card);
            return wrapper;
        }

        function renderCreationCardLauncher(card) {
            if (!card?.id) return null;
            workbenchState.cards.set(String(card.id), card);
            const launcher = document.createElement('section');
            launcher.className = 'message-card-launcher';
            launcher.dataset.cardLauncherId = String(card.id);
            launcher.innerHTML = `
                <div class="message-card-launcher-icon" aria-hidden="true">◇</div>
                <div class="message-card-launcher-copy">
                    <strong>${escapeHtml(card.title || '广告创建参数')}</strong>
                    <span class="message-card-launcher-status">已整理参数，可在右侧继续</span>
                </div>
                <button type="button" class="message-card-launcher-button">打开工作区</button>
            `;
            launcher.querySelector('button')?.addEventListener('click', () => reopenCreationCard(card.id));
            updateCreationCardLauncher(card);
            return launcher;
        }

        function updateCreationCardLauncher(card) {
            if (!card?.id) return;
            const launcher = document.querySelector(`[data-card-launcher-id="${CSS.escape(String(card.id))}"]`);
            const status = launcher?.querySelector('.message-card-launcher-status');
            if (status && typeof creationCardStatus === 'function') status.textContent = creationCardStatus(card);
            const title = launcher?.querySelector('.message-card-launcher-copy strong');
            if (title) title.textContent = card.title || '广告创建参数';
            updateCreationWorkbenchCount();
        }

        function reopenCreationCard(cardId) {
            const card = workbenchState.cards.get(String(cardId)) || creationCardState?.get(cardId);
            if (!card) return;
            renderCreationCardInWorkbench(card);
        }

        function resetCreationWorkbench() {
            workbenchState.activeCardId = null;
            workbenchState.cards.clear();
            document.getElementById('creation-workbench-host')?.replaceChildren();
            document.getElementById('confirmation-workbench-host')?.replaceChildren();
            setWorkbenchView('trace');
            closeAgentWorkbench();
            updateCreationWorkbenchCount();
        }

        function clearWorkbenchConfirmation() {
            document.getElementById('confirmation-workbench-host')?.replaceChildren();
            const host = document.getElementById('creation-workbench-host');
            if (host) host.hidden = false;
        }
