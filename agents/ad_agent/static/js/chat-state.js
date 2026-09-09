        let pendingRequest = null;
        let isSending = false;
        let sessionId = null;
        let apiCallCount = 0;
        let conversationCount = 0;
        let serviceApiKey = '';
        let conversationHistory = [];
        let selectedConversationId = null;
        let conversationHistoryRequest = 0;
        let historySelectionMode = false;
        const selectedConversationIds = new Set();
        let historySearchQuery = '';
        let pendingConversationDeleteIds = [];
        let pendingConversationRenameId = null;
        const loadedConversationTurnIds = new Set();
        let workspaceTheme = 'dark';
        const creationCardState = new Map();
        const creationCardEvaluationTimers = new Map();
        const creationCardEvaluationRevisions = new Map();
        const creationDirectoryCollapseState = new Map();
        let pendingBlueprintRequest = null;
        let pendingCreationReview = null;
        const skillState = {
            versions: [],
            selected: null,
            detail: null,
            files: [],
            readOnly: false,
            evaluationTimer: null,
            expanded: new Set(),
            activeFilePath: 'SKILL.md',
            previewMode: false,
        };
        const blueprintState = {
            items: [],
            formats: [],
            selected: null,
            tools: [],
            values: {},
            previousValues: {},
            evaluation: null,
            loading: false,
            accountId: '',
            localFiles: {},
            selectionTokens: {},
            selectionTokenTools: {},
            lookupOptions: {},
            listQuery: '',
            listProvider: 'all',
            templates: [],
            selectedTemplateId: '',
            templatePanelOpen: false,
            templateSaveAsNew: false,
            mode: 'wizard',
        };
        const knowledgeState = { items: [], selectedKey: '', summary: '', summaryMode: 'lexical', managedItems: [], editingDocumentId: '' };

        const TRACE_STATUS_LABELS = {
            planned: '计划中', running: '运行中', succeeded: '已成功',
            failed: '失败', skipped: '已跳过', awaiting_confirmation: '待确认',
            unknown: '待命', recovery_required: '需恢复'
        };
        let traceState = { nodes: [], events: [], selectedId: null, collapsed: false, expanded: false, activeTurn: 0, traceId: null, status: 'unknown', orderCounter: 0 };
        let durableRunPollTimer = null;
        let durableRunPollToken = 0;
        let activeDurableRunId = null;
        let durableRunSeq = 0;
        let monitoringRefreshTimer = null;
        let monitoringRequestToken = 0;

        function traceStatusLabel(status) {
            return TRACE_STATUS_LABELS[status] || '未知';
        }

        function traceMark(kind) {
            const marks = { Agent: 'A', Skill: 'S', Guard: 'G', Tool: 'T', Meta: 'M', Google: 'G', TikTok: 'T', DV360: 'D', stage: '✦', intent: '◎', analysis: '◌', reply: '↗' };
            return marks[kind] || '·';
        }

        function traceEventLabel(event) {
            const labels = {
                start: 'Agent 回合开始', plan: '执行计划已生成', node_started: 'Tool 开始执行',
                node_status: 'Tool 状态更新', confirmation: '等待用户确认', reply: '回复已准备',
                stage_started: '阶段开始', stage_status: '阶段状态更新',
                done: '回合结束', error: '执行异常'
            };
            const node = event.node_id ? ` · ${event.title || event.tool || event.node_id}` : '';
            return `${labels[event.type] || '执行事件'}${node}`;
        }

        function pushTraceEvent(event) {
            traceState.events.push({ ...event, receivedAt: Date.now() });
            if (traceState.events.length > 80) traceState.events.shift();
        }

        let traceFilter = { platform: 'all', status: 'all', kind: 'all' };
        let workspaceMode = {
            mode: '', loading: false, saving: false, liveAvailable: false, liveReason: ''
        };

