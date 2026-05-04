import { Component, EventEmitter, Input, OnChanges, Output, SimpleChanges } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Qualifier, QualifierCreate, QualifierUpdate } from '../models/qualifier.model';
import { QualifiersService } from '../services/qualifiers.service';
import { AuthService } from '../services/auth.service';

type TrackedField = { name: string; type: 'string' | 'boolean' | 'array' | 'number'; required: boolean };
type EditorTab = 'offer' | 'learn' | 'policy' | 'graph' | 'advanced';
type SuggestedField = TrackedField & { label: string; description: string };

@Component({
  selector: 'app-qualifier-editor',
  standalone: true,
  imports: [CommonModule, FormsModule],
  template: `
    <div class="editor-shell">
      <div class="editor-header">
        <div>
          <h2>{{ qualifier ? 'Edit ACE e-Counter' : 'Create ACE e-Counter' }}</h2>
          <p>Configure business fit, what the agent should learn, and how it moves conversations forward.</p>
        </div>
        <button class="btn-close" (click)="cancelled.emit()">✕</button>
      </div>

      <div class="editor-tabs">
        <button [class.active]="activeTab==='offer'" (click)="activeTab='offer'">Offer</button>
        <button [class.active]="activeTab==='learn'" (click)="activeTab='learn'">Learn</button>
        <button [class.active]="activeTab==='policy'" (click)="activeTab='policy'">Next step policy</button>
        <button [class.active]="activeTab==='graph'" (click)="activeTab='graph'">Graph view</button>
        <button [class.active]="activeTab==='advanced'" (click)="activeTab='advanced'">Advanced</button>
      </div>

      <div class="editor-body" *ngIf="activeTab==='offer'">
        <div class="panel-intro">
          <strong>What this edits</strong>
          <span>Who ACE e-Counter is, what it should help with, and how it should sound.</span>
        </div>

        <div class="grid two">
          <label>
            <span>Name *</span>
            <input [(ngModel)]="name" placeholder="ACE e-Counter" />
          </label>

          <label>
            <span>Slug *</span>
            <input [(ngModel)]="slug" placeholder="ace-e-counter" />
          </label>
        </div>

        <div class="grid two">
          <label>
            <span>Assistant style</span>
            <input [(ngModel)]="assistantStyle" placeholder="friendly, concise, consultative" />
          </label>

          <label>
            <span>Contact capture policy</span>
            <input [(ngModel)]="contactCapturePolicy" placeholder="when_high_intent_or_explicit" />
          </label>
        </div>

        <label>
          <span>What ACE e-Counter should achieve</span>
          <textarea [(ngModel)]="goalDefinition" rows="4" placeholder="Example: understand whether ACE can help this business, learn how they currently get customers, surface pain points, and move strong leads toward the next step."></textarea>
        </label>

        <label>
          <span>Core business-fit instructions *</span>
          <textarea [(ngModel)]="systemPrompt" rows="10" placeholder="Explain ACE e-Counter accurately. Treat real businesses as valid prospects even if they are small, informal, or offline-first. Do not pretend ACE sells unrelated products. Ask one useful follow-up question when needed."></textarea>
        </label>

        <div class="note-card">
          <strong>Recommended content</strong>
          <ul>
            <li>What ACE e-Counter actually helps with</li>
            <li>What should route out: support, jobs, vendors, nonsense</li>
            <li>That small/local businesses can still be valid prospects</li>
            <li>That the assistant should not invent meaning if unclear</li>
          </ul>
        </div>
      </div>

      <div class="editor-body" *ngIf="activeTab==='learn'">
        <div class="panel-intro">
          <strong>What this edits</strong>
          <span>Which business facts the agent should learn and keep in profile state.</span>
        </div>

        <div class="suggest-grid">
          <button type="button" class="suggest-card" *ngFor="let field of suggestedFields" (click)="addSuggestedField(field)" [disabled]="hasField(field.name)">
            <strong>{{ field.label }}</strong>
            <span>{{ field.description }}</span>
            <small>{{ hasField(field.name) ? 'Added' : 'Add field' }}</small>
          </button>
        </div>

        <div class="field-builder">
          <div class="field-builder__header">
            <span>Captured fields</span>
            <button type="button" class="btn-secondary" (click)="addField()">+ Custom field</button>
          </div>

          <div class="field-builder__columns" *ngIf="trackedFields.length">
            <span>Field</span>
            <span>Answer format</span>
            <span>Required</span>
            <span></span>
          </div>

          <div class="field-row" *ngFor="let field of trackedFields; let i = index">
            <input [(ngModel)]="field.name" placeholder="field name" />
            <div class="field-type-wrap">
              <select class="field-type-select" [(ngModel)]="field.type">
                <option value="string">Text answer</option>
                <option value="boolean">Yes / No</option>
                <option value="array">List / multiple items</option>
                <option value="number">Number</option>
              </select>
              <div class="field-type-hint">{{ fieldTypeHint(field.type) }}</div>
            </div>
            <label class="req-toggle"><input type="checkbox" [(ngModel)]="field.required" /> <span>required</span></label>
            <button type="button" class="btn-close small" (click)="removeField(i)">✕</button>
          </div>
        </div>
      </div>

      <div class="editor-body" *ngIf="activeTab==='policy'">
        <div class="panel-intro">
          <strong>What this edits</strong>
          <span>How the agent qualifies, confirms, escalates, and offers takeover.</span>
        </div>

        <div class="grid three">
          <label>
            <span>Hot threshold</span>
            <input type="number" [(ngModel)]="hotMin" min="0" max="100" />
          </label>
          <label>
            <span>Warm threshold</span>
            <input type="number" [(ngModel)]="warmMin" min="0" max="100" />
          </label>
          <label>
            <span>Max clarifying questions</span>
            <input type="number" [(ngModel)]="maxClarifyingQuestions" min="0" max="20" />
          </label>
        </div>

        <div class="grid two">
          <div class="policy-card">
            <h3>Confidence thresholds</h3>
            <label>
              <span>Overall confidence for takeover</span>
              <input type="number" [(ngModel)]="overallMinForTakeover" min="0" max="1" step="0.05" />
            </label>
            <label>
              <span>Field confidence for fact persistence</span>
              <input type="number" [(ngModel)]="fieldMinForFactPersistence" min="0" max="1" step="0.05" />
            </label>
          </div>

          <div class="policy-card">
            <h3>Takeover policy</h3>
            <label class="checkline"><input type="checkbox" [(ngModel)]="offerOnExplicitHumanRequest" /> <span>Offer takeover on explicit human request</span></label>
            <label class="checkline"><input type="checkbox" [(ngModel)]="offerOnHotBand" /> <span>Offer takeover for hot leads</span></label>
            <label class="checkline"><input type="checkbox" [(ngModel)]="offerOnVideoEligible" /> <span>Allow video path in takeover policy</span></label>
          </div>
        </div>

        <div class="grid two">
          <div class="policy-card">
            <h3>Video offer policy</h3>
            <label class="checkline"><input type="checkbox" [(ngModel)]="videoEnabled" /> <span>Enable video offer</span></label>
            <label class="checkline"><input type="checkbox" [(ngModel)]="videoRequiresTakeover" /> <span>Only allow video if takeover is already eligible</span></label>
            <label class="checkline"><input type="checkbox" [(ngModel)]="operatorCanOfferVideoManually" /> <span>Let operators offer video manually</span></label>
          </div>

          <div class="policy-card">
            <h3>Operator summary</h3>
            <ul>
              <li>Required fields: {{ requiredFieldsPreview() }}</li>
              <li>Hot / warm bands: {{ hotMin }} / {{ warmMin }}</li>
              <li>Clarifying turns before stronger action: {{ maxClarifyingQuestions }}</li>
              <li>Takeover confidence floor: {{ overallMinForTakeover }}</li>
            </ul>
          </div>
        </div>
      </div>

      <div class="editor-body" *ngIf="activeTab==='graph'">
        <div class="panel-intro">
          <strong>Fixed runtime graph</strong>
          <span>The runtime stays product-owned. This screen shows how your current configuration shapes each node.</span>
        </div>

        <div class="graph-flow">
          <div class="graph-node">
            <div class="graph-node__eyebrow">Node 1</div>
            <h3>Interpret turn</h3>
            <p>Classifies the conversation, updates business context, and assesses ACE fit from recent messages.</p>
            <ul>
              <li>Uses: system prompt + goal + recent messages</li>
              <li>Tracks: {{ requiredFieldsPreview() }}</li>
              <li>Stores: visitor type, fit, supporting business facts</li>
            </ul>
          </div>

          <div class="graph-arrow">→</div>

          <div class="graph-node">
            <div class="graph-node__eyebrow">Node 2</div>
            <h3>Decide next step</h3>
            <p>Chooses the next action and writes the reply using the interpreted business context.</p>
            <ul>
              <li>Style: {{ assistantStyle || 'friendly, concise, consultative' }}</li>
              <li>Max clarifying questions: {{ maxClarifyingQuestions }}</li>
              <li>Takeover on explicit human request: {{ offerOnExplicitHumanRequest ? 'yes' : 'no' }}</li>
            </ul>
          </div>

          <div class="graph-arrow">→</div>

          <div class="graph-node graph-node--muted">
            <div class="graph-node__eyebrow">Persist</div>
            <h3>Save result</h3>
            <p>Stores profile, confidence, score band, and recommended next action for the dashboard and chat runtime.</p>
          </div>
        </div>
      </div>

      <div class="editor-body" *ngIf="activeTab==='advanced'">
        <div class="panel-intro">
          <strong>Advanced</strong>
          <span>Low-level payload preview and optional notes. Use this only if you know why.</span>
        </div>

        <label>
          <span>Version notes</span>
          <input [(ngModel)]="versionNotes" placeholder="Updated from dashboard editor" />
        </label>

        <label>
          <span>Scoring rules JSON</span>
          <textarea [(ngModel)]="scoringRulesText" rows="6"></textarea>
        </label>

        <details>
          <summary>Generated payload preview</summary>
          <label>
            <span>Field schema</span>
            <textarea [ngModel]="generatedFieldSchemaText()" rows="10" readonly></textarea>
          </label>
          <label>
            <span>Confidence thresholds</span>
            <textarea [ngModel]="generatedConfidenceThresholdsText()" rows="6" readonly></textarea>
          </label>
          <label>
            <span>Takeover rules</span>
            <textarea [ngModel]="generatedTakeoverRulesText()" rows="6" readonly></textarea>
          </label>
          <label>
            <span>Video offer rules</span>
            <textarea [ngModel]="generatedVideoOfferRulesText()" rows="6" readonly></textarea>
          </label>
        </details>
      </div>

      <div class="error" *ngIf="errorMessage">⚠️ {{ errorMessage }}</div>
      <div class="success" *ngIf="successMessage">✅ {{ successMessage }}</div>

      <div class="actions">
        <button class="btn-secondary" (click)="cancelled.emit()" [disabled]="saving">Cancel</button>
        <button class="btn-primary" (click)="save()" [disabled]="saving || !isValid()">
          {{ saving ? 'Saving...' : (qualifier ? 'Save ACE e-Counter' : 'Create ACE e-Counter') }}
        </button>
      </div>
    </div>
  `,
  styles: [`
    .editor-shell { background:#fff; border-radius:12px; padding:24px; box-shadow:0 6px 24px rgba(0,0,0,.08); }
    .editor-header{ display:flex; justify-content:space-between; align-items:flex-start; gap:16px; margin-bottom:18px; }
    .editor-header h2{ margin:0 0 4px; }
    .editor-header p{ margin:0; color:#6b7280; max-width:720px; }
    .editor-tabs{ display:flex; flex-wrap:wrap; gap:8px; margin-bottom:18px; }
    .editor-tabs button{ border:1px solid #d1d5db; background:#fff; color:#374151; border-radius:999px; padding:8px 14px; cursor:pointer; font-weight:700; }
    .editor-tabs button.active{ background:#111827; color:#fff; border-color:#111827; }
    .editor-body{ display:flex; flex-direction:column; gap:14px; }
    .panel-intro{ display:flex; flex-direction:column; gap:4px; padding:12px 14px; background:#f8fafc; border:1px solid #e2e8f0; border-radius:10px; }
    .panel-intro strong{ color:#0f172a; }
    .panel-intro span{ color:#475569; }
    .grid{ display:grid; gap:14px; }
    .grid.two{ grid-template-columns:1fr 1fr; }
    .grid.three{ grid-template-columns:1fr 1fr 1fr; }
    label{ display:flex; flex-direction:column; gap:6px; font-size:13px; color:#374151; }
    label span{ font-weight:600; }
    input, textarea, select{ width:100%; padding:10px 12px; border:1px solid #d1d5db; border-radius:8px; font:inherit; box-sizing:border-box; background:#fff; }
    textarea{ resize:vertical; }
    .note-card, .policy-card{ border:1px solid #e5e7eb; border-radius:10px; padding:14px; background:#fafafa; }
    .note-card strong, .policy-card h3{ display:block; margin:0 0 10px; color:#111827; }
    .note-card ul, .policy-card ul{ margin:0; padding-left:18px; color:#4b5563; display:grid; gap:6px; }
    .suggest-grid{ display:grid; grid-template-columns:repeat(auto-fit, minmax(190px, 1fr)); gap:10px; }
    .suggest-card{ text-align:left; border:1px solid #e5e7eb; background:#fff; border-radius:10px; padding:12px; cursor:pointer; display:flex; flex-direction:column; gap:6px; }
    .suggest-card strong{ color:#111827; }
    .suggest-card span{ color:#4b5563; font-size:13px; }
    .suggest-card small{ color:#6b7280; font-weight:700; }
    .suggest-card:disabled{ opacity:.55; cursor:not-allowed; }
    .field-builder{ border:1px solid #e5e7eb; border-radius:10px; padding:14px; background:#fafafa; overflow:hidden; }
    .field-builder__header{ display:flex; justify-content:space-between; align-items:center; margin-bottom:10px; font-weight:700; }
    .field-builder__columns,
    .field-row{ display:grid; grid-template-columns:minmax(0, 1.8fr) minmax(0, 1.2fr) 110px 40px; gap:10px; align-items:start; }
    .field-builder__columns{ margin-bottom:8px; color:#6b7280; font-size:12px; font-weight:700; text-transform:uppercase; letter-spacing:.04em; }
    .field-row{ margin-bottom:10px; padding:10px; background:#fff; border:1px solid #e5e7eb; border-radius:10px; }
    .field-row > input{ min-width:0; }
    .field-type-wrap{ min-width:0; }
    .field-type-select{ appearance:none; -webkit-appearance:none; -moz-appearance:none; padding-right:36px; background-image:linear-gradient(45deg, transparent 50%, #6b7280 50%), linear-gradient(135deg, #6b7280 50%, transparent 50%); background-position:calc(100% - 18px) calc(50% - 3px), calc(100% - 12px) calc(50% - 3px); background-size:6px 6px, 6px 6px; background-repeat:no-repeat; }
    .field-type-hint{ margin-top:4px; font-size:12px; line-height:1.35; color:#6b7280; }
    .req-toggle{ flex-direction:row; align-items:center; justify-self:start; gap:8px; white-space:nowrap; padding-top:10px; }
    .req-toggle input, .checkline input{ width:auto; }
    .small{ font-size:16px; padding:4px 8px; justify-self:end; align-self:start; }
    .checkline{ flex-direction:row; align-items:center; gap:10px; }
    .graph-flow{ display:grid; grid-template-columns:1fr 40px 1fr 40px 1fr; gap:12px; align-items:center; }
    .graph-node{ border:1px solid #dbeafe; background:#eff6ff; border-radius:12px; padding:16px; }
    .graph-node--muted{ background:#f8fafc; border-color:#e2e8f0; }
    .graph-node__eyebrow{ color:#1d4ed8; font-size:12px; font-weight:800; text-transform:uppercase; letter-spacing:.06em; margin-bottom:6px; }
    .graph-node h3{ margin:0 0 8px; color:#111827; }
    .graph-node p{ margin:0 0 10px; color:#475569; }
    .graph-node ul{ margin:0; padding-left:18px; color:#475569; display:grid; gap:6px; }
    .graph-arrow{ text-align:center; font-size:28px; font-weight:900; color:#94a3b8; }
    details{ border:1px solid #e5e7eb; border-radius:8px; padding:12px; background:#fafafa; }
    summary{ cursor:pointer; font-weight:700; margin-bottom:10px; }
    .actions{ display:flex; justify-content:flex-end; gap:10px; margin-top:18px; }
    .btn-primary,.btn-secondary,.btn-close{ border:none; border-radius:8px; cursor:pointer; }
    .btn-primary{ background:#2563eb; color:#fff; padding:10px 16px; }
    .btn-secondary{ background:#e5e7eb; color:#111827; padding:10px 16px; }
    .btn-close{ background:transparent; font-size:22px; padding:2px 8px; }
    .error{ color:#b91c1c; background:#fee2e2; padding:10px 12px; border-radius:8px; margin-top:14px; }
    .success{ color:#166534; background:#dcfce7; padding:10px 12px; border-radius:8px; margin-top:14px; }
    @media (max-width: 960px){
      .grid.two, .grid.three, .graph-flow{ grid-template-columns:1fr; }
      .graph-arrow{ display:none; }
    }
    @media (max-width: 820px){
      .field-builder__columns{ display:none; }
      .field-row{ grid-template-columns:1fr; }
      .req-toggle{ white-space:normal; }
    }
  `]
})
export class QualifierEditorComponent implements OnChanges {
  @Input() qualifier: Qualifier | null = null;
  @Output() saved = new EventEmitter<void>();
  @Output() cancelled = new EventEmitter<void>();

  activeTab: EditorTab = 'offer';

  name = 'ACE e-Counter';
  slug = 'ace-e-counter';
  systemPrompt = '';
  assistantStyle = 'friendly, concise, consultative';
  goalDefinition = '';
  trackedFields: TrackedField[] = [
    { name: 'business_type', type: 'string', required: false },
    { name: 'customer_source', type: 'string', required: false },
    { name: 'pain_points', type: 'array', required: false },
    { name: 'desired_outcome', type: 'string', required: false },
    { name: 'contact_email', type: 'string', required: false },
    { name: 'contact_phone', type: 'string', required: false },
  ];

  suggestedFields: SuggestedField[] = [
    { name: 'business_type', type: 'string', required: false, label: 'Business type', description: 'What kind of business the visitor runs.' },
    { name: 'customer_source', type: 'string', required: false, label: 'Customer source', description: 'How they currently get customers or inquiries.' },
    { name: 'sales_motion', type: 'string', required: false, label: 'Sales motion', description: 'How they currently sell or handle interest.' },
    { name: 'growth_constraint', type: 'string', required: false, label: 'Growth constraint', description: 'What is limiting growth right now.' },
    { name: 'pain_points', type: 'array', required: false, label: 'Pain points', description: 'Main problems hurting results or operations.' },
    { name: 'desired_outcome', type: 'string', required: false, label: 'Desired outcome', description: 'What success looks like for this lead.' },
    { name: 'contact_email', type: 'string', required: false, label: 'Email', description: 'Capture email when the conversation earns it.' },
    { name: 'contact_phone', type: 'string', required: false, label: 'Phone', description: 'Capture phone when fast follow-up matters.' },
    { name: 'human_request', type: 'boolean', required: false, label: 'Human request', description: 'Did the visitor explicitly ask for a person?' },
  ];

  scoringRulesText = JSON.stringify({ notes: 'Runtime metadata only' }, null, 2);
  ragEnabled = false;
  maxClarifyingQuestions = 3;
  contactCapturePolicy = 'when_high_intent_or_explicit';
  hotMin = 80;
  warmMin = 50;

  overallMinForTakeover = 0.7;
  fieldMinForFactPersistence = 0.6;
  offerOnExplicitHumanRequest = true;
  offerOnHotBand = true;
  offerOnVideoEligible = true;
  videoEnabled = true;
  videoRequiresTakeover = true;
  operatorCanOfferVideoManually = true;

  versionNotes = 'Updated from dashboard editor';
  saving = false;
  errorMessage = '';
  successMessage = '';

  constructor(
    private qualifiersService: QualifiersService,
    private authService: AuthService
  ) {}

  ngOnChanges(changes: SimpleChanges): void {
    if (changes['qualifier']) this.fillFromQualifier();
  }

  private fillFromQualifier() {
    if (!this.qualifier) {
      this.activeTab = 'offer';
      this.name = 'ACE e-Counter';
      this.slug = 'ace-e-counter';
      this.systemPrompt = '';
      this.assistantStyle = 'friendly, concise, consultative';
      this.goalDefinition = '';
      this.trackedFields = [
        { name: 'business_type', type: 'string', required: false },
        { name: 'customer_source', type: 'string', required: false },
        { name: 'pain_points', type: 'array', required: false },
        { name: 'desired_outcome', type: 'string', required: false },
        { name: 'contact_email', type: 'string', required: false },
        { name: 'contact_phone', type: 'string', required: false },
      ];
      this.scoringRulesText = JSON.stringify({ notes: 'Runtime metadata only' }, null, 2);
      this.ragEnabled = false;
      this.maxClarifyingQuestions = 3;
      this.contactCapturePolicy = 'when_high_intent_or_explicit';
      this.hotMin = 80;
      this.warmMin = 50;
      this.overallMinForTakeover = 0.7;
      this.fieldMinForFactPersistence = 0.6;
      this.offerOnExplicitHumanRequest = true;
      this.offerOnHotBand = true;
      this.offerOnVideoEligible = true;
      this.videoEnabled = true;
      this.videoRequiresTakeover = true;
      this.operatorCanOfferVideoManually = true;
      this.versionNotes = 'Updated from dashboard editor';
      this.successMessage = '';
      this.errorMessage = '';
      return;
    }

    this.name = this.qualifier.name;
    this.slug = this.qualifier.slug;
    this.systemPrompt = this.qualifier.system_prompt || '';
    this.assistantStyle = this.qualifier.assistant_style || 'friendly, concise, consultative';
    this.goalDefinition = this.qualifier.goal_definition || '';
    this.trackedFields = this.toTrackedFields(this.qualifier.field_schema || {}, this.qualifier.required_fields || []);
    this.scoringRulesText = JSON.stringify(this.qualifier.scoring_rules || { notes: 'Runtime metadata only' }, null, 2);
    this.ragEnabled = !!this.qualifier.rag_enabled;
    this.maxClarifyingQuestions = this.qualifier.max_clarifying_questions ?? 3;
    this.contactCapturePolicy = this.qualifier.contact_capture_policy || 'when_high_intent_or_explicit';
    this.hotMin = this.qualifier.band_thresholds?.hot_min ?? 80;
    this.warmMin = this.qualifier.band_thresholds?.warm_min ?? 50;
    this.overallMinForTakeover = this.qualifier.confidence_thresholds?.overall_min_for_takeover ?? 0.7;
    this.fieldMinForFactPersistence = this.qualifier.confidence_thresholds?.field_min_for_fact_persistence ?? 0.6;
    this.offerOnExplicitHumanRequest = this.qualifier.takeover_rules?.offer_on_explicit_human_request ?? true;
    this.offerOnHotBand = this.qualifier.takeover_rules?.offer_on_hot_band ?? true;
    this.offerOnVideoEligible = this.qualifier.takeover_rules?.offer_on_video_eligible ?? true;
    this.videoEnabled = this.qualifier.video_offer_rules?.enabled ?? true;
    this.videoRequiresTakeover = this.qualifier.video_offer_rules?.requires_takeover_eligible ?? true;
    this.operatorCanOfferVideoManually = this.qualifier.video_offer_rules?.operator_can_offer_manually ?? true;
    this.versionNotes = this.qualifier.version_notes || 'Updated from dashboard editor';
    this.successMessage = '';
    this.errorMessage = '';
  }

  isValid(): boolean {
    return !!this.name.trim() && !!this.slug.trim() && !!this.systemPrompt.trim() && this.trackedFields.some(f => !!f.name.trim());
  }

  hasField(name: string): boolean {
    return this.trackedFields.some(field => field.name.trim() === name);
  }

  addSuggestedField(field: SuggestedField) {
    if (this.hasField(field.name)) return;
    this.trackedFields = [...this.trackedFields, { name: field.name, type: field.type, required: field.required }];
  }

  addField() {
    this.trackedFields = [...this.trackedFields, { name: '', type: 'string', required: false }];
  }

  removeField(index: number) {
    this.trackedFields = this.trackedFields.filter((_, i) => i !== index);
  }

  fieldTypeHint(type: TrackedField['type']): string {
    switch (type) {
      case 'boolean':
        return 'Best for yes/no signals like “asked for human help”.';
      case 'array':
        return 'Best when the agent may capture multiple items, like pain points or objections.';
      case 'number':
        return 'Best for values like budget amount or monthly volume.';
      case 'string':
      default:
        return 'Best for normal text like business type, customer source, or desired outcome.';
    }
  }

  requiredFieldsPreview(): string {
    const required = this.trackedFields.filter(f => f.required && f.name.trim()).map(f => f.name.trim());
    return required.length ? required.join(', ') : 'none';
  }

  generatedFieldSchemaText(): string {
    return JSON.stringify(this.buildFieldSchema(), null, 2);
  }

  generatedConfidenceThresholdsText(): string {
    return JSON.stringify(this.buildConfidenceThresholds(), null, 2);
  }

  generatedTakeoverRulesText(): string {
    return JSON.stringify(this.buildTakeoverRules(), null, 2);
  }

  generatedVideoOfferRulesText(): string {
    return JSON.stringify(this.buildVideoOfferRules(), null, 2);
  }

  private buildFieldSchema(): Record<string, any> {
    const out: Record<string, any> = {};
    for (const field of this.trackedFields) {
      const name = (field.name || '').trim();
      if (!name) continue;
      out[name] = { type: field.type, required: !!field.required };
    }
    return out;
  }

  private buildConfidenceThresholds(): Record<string, any> {
    return {
      overall_min_for_takeover: Number(this.overallMinForTakeover),
      field_min_for_fact_persistence: Number(this.fieldMinForFactPersistence),
    };
  }

  private buildTakeoverRules(): Record<string, any> {
    return {
      offer_on_explicit_human_request: !!this.offerOnExplicitHumanRequest,
      offer_on_hot_band: !!this.offerOnHotBand,
      offer_on_video_eligible: !!this.offerOnVideoEligible,
    };
  }

  private buildVideoOfferRules(): Record<string, any> {
    return {
      enabled: !!this.videoEnabled,
      requires_takeover_eligible: !!this.videoRequiresTakeover,
      operator_can_offer_manually: !!this.operatorCanOfferVideoManually,
    };
  }

  private toTrackedFields(fieldSchema: Record<string, any>, requiredFields: string[]): TrackedField[] {
    const keys = Object.keys(fieldSchema || {});
    if (!keys.length) {
      return [
        { name: 'business_type', type: 'string', required: false },
        { name: 'customer_source', type: 'string', required: false },
        { name: 'pain_points', type: 'array', required: false },
        { name: 'desired_outcome', type: 'string', required: false },
      ];
    }
    return keys.map((key) => ({
      name: key,
      type: (fieldSchema[key]?.type || 'string') as any,
      required: !!fieldSchema[key]?.required || requiredFields.includes(key),
    }));
  }

  save() {
    this.errorMessage = '';
    this.successMessage = '';

    let scoringRules: any;
    try {
      scoringRules = JSON.parse(this.scoringRulesText || '{}');
    } catch {
      this.errorMessage = 'Scoring rules JSON is invalid.';
      this.activeTab = 'advanced';
      return;
    }

    const fieldSchema = this.buildFieldSchema();
    const confidenceThresholds = this.buildConfidenceThresholds();
    const takeoverRules = this.buildTakeoverRules();
    const videoOfferRules = this.buildVideoOfferRules();
    const requiredFields = this.trackedFields.filter(f => f.required && f.name.trim()).map(f => f.name.trim());

    const basePayload = {
      name: this.name.trim(),
      slug: this.slug.trim(),
      status: this.qualifier?.status || 'draft' as const,
      system_prompt: this.systemPrompt.trim(),
      assistant_style: this.assistantStyle.trim(),
      goal_definition: this.goalDefinition.trim(),
      field_schema: fieldSchema,
      required_fields: requiredFields,
      scoring_rules: scoringRules,
      band_thresholds: { hot_min: Number(this.hotMin), warm_min: Number(this.warmMin), cold_max: Math.max(Number(this.warmMin) - 1, 0) },
      confidence_thresholds: confidenceThresholds,
      takeover_rules: takeoverRules,
      video_offer_rules: videoOfferRules,
      rag_enabled: this.ragEnabled,
      knowledge_source_ids: [],
      max_clarifying_questions: Number(this.maxClarifyingQuestions),
      contact_capture_policy: this.contactCapturePolicy.trim(),
      version: this.qualifier?.version || 1,
      version_notes: this.versionNotes.trim() || 'Updated from dashboard editor'
    };

    this.saving = true;
    if (this.qualifier) {
      const payload: QualifierUpdate = basePayload;
      this.qualifiersService.updateQualifier(this.qualifier.id, payload).subscribe({
        next: () => {
          this.saving = false;
          this.successMessage = 'ACE e-Counter saved.';
          this.saved.emit();
        },
        error: (err) => {
          this.saving = false;
          this.errorMessage = err?.error?.detail || 'Failed to save qualifier.';
        }
      });
    } else {
      const payload: QualifierCreate = {
        organization_id: this.authService.getCurrentUser()?.organization_id || 1,
        ...basePayload,
      };
      this.qualifiersService.createQualifier(payload).subscribe({
        next: () => {
          this.saving = false;
          this.successMessage = 'ACE e-Counter created.';
          this.saved.emit();
        },
        error: (err) => {
          this.saving = false;
          this.errorMessage = err?.error?.detail || 'Failed to create qualifier.';
        }
      });
    }
  }
}
