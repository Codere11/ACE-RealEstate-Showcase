import { Component, EventEmitter, Input, OnChanges, Output, SimpleChanges } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Qualifier, QualifierCreate, QualifierUpdate } from '../models/qualifier.model';
import { QualifiersService } from '../services/qualifiers.service';
import { AuthService } from '../services/auth.service';

type TrackedField = { name: string; type: 'string' | 'boolean' | 'array' | 'number'; required: boolean };

@Component({
  selector: 'app-qualifier-editor',
  standalone: true,
  imports: [CommonModule, FormsModule],
  template: `
    <div class="editor-shell">
      <div class="editor-header">
        <h2>{{ qualifier ? 'Edit AI Qualifier' : 'Create AI Qualifier' }}</h2>
        <button class="btn-close" (click)="cancelled.emit()">✕</button>
      </div>

      <div class="editor-body">
        <div class="grid two">
          <label>
            <span>Name *</span>
            <input [(ngModel)]="name" placeholder="Default AI Qualifier" />
          </label>

          <label>
            <span>Slug *</span>
            <input [(ngModel)]="slug" placeholder="default-ai-qualifier" />
          </label>
        </div>

        <div class="grid two">
          <label>
            <span>How should the agent sound?</span>
            <input [(ngModel)]="assistantStyle" placeholder="friendly, sharp, consultative" />
          </label>

          <label>
            <span>When should contact be pushed?</span>
            <input [(ngModel)]="contactCapturePolicy" placeholder="when_high_intent_or_explicit" />
          </label>
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

        <label>
          <span>What should the agent achieve?</span>
          <textarea [(ngModel)]="goalDefinition" rows="3" placeholder="Understand intent, answer well, qualify seriously, and move good leads toward takeover."></textarea>
        </label>

        <label>
          <span>Core instructions for the agent *</span>
          <textarea [(ngModel)]="systemPrompt" rows="7" placeholder="Answer the user's question first. Qualify naturally. Ask one smart follow-up when needed. Do not sound robotic."></textarea>
        </label>

        <div class="field-builder">
          <div class="field-builder__header">
            <span>What should the agent capture?</span>
            <button type="button" class="btn-secondary" (click)="addField()">+ Add field</button>
          </div>
          <div class="field-row" *ngFor="let field of trackedFields; let i = index">
            <input [(ngModel)]="field.name" placeholder="field name (e.g. budget)" />
            <select [(ngModel)]="field.type">
              <option value="string">string</option>
              <option value="boolean">boolean</option>
              <option value="array">array</option>
              <option value="number">number</option>
            </select>
            <label class="req-toggle"><input type="checkbox" [(ngModel)]="field.required" /> required</label>
            <button type="button" class="btn-close small" (click)="removeField(i)">✕</button>
          </div>
        </div>

        <div class="grid two">
          <label class="checkline">
            <input type="checkbox" [(ngModel)]="ragEnabled" />
            <span>RAG enabled</span>
          </label>
        </div>

        <details>
          <summary>Advanced settings</summary>
          <label>
            <span>Generated field schema JSON</span>
            <textarea [ngModel]="generatedFieldSchemaText()" rows="8" readonly></textarea>
          </label>
          <label>
            <span>Confidence thresholds JSON</span>
            <textarea [(ngModel)]="confidenceThresholdsText" rows="5"></textarea>
          </label>
          <label>
            <span>Takeover rules JSON</span>
            <textarea [(ngModel)]="takeoverRulesText" rows="5"></textarea>
          </label>
          <label>
            <span>Video offer rules JSON</span>
            <textarea [(ngModel)]="videoOfferRulesText" rows="5"></textarea>
          </label>
          <label>
            <span>Scoring rules JSON</span>
            <textarea [(ngModel)]="scoringRulesText" rows="5"></textarea>
          </label>
        </details>

        <div class="error" *ngIf="errorMessage">⚠️ {{ errorMessage }}</div>
        <div class="success" *ngIf="successMessage">✅ {{ successMessage }}</div>

        <div class="actions">
          <button class="btn-secondary" (click)="cancelled.emit()" [disabled]="saving">Cancel</button>
          <button class="btn-primary" (click)="save()" [disabled]="saving || !isValid()">
            {{ saving ? 'Saving...' : (qualifier ? 'Save Qualifier' : 'Create Qualifier') }}
          </button>
        </div>
      </div>
    </div>
  `,
  styles: [`
    .editor-shell { background:#fff; border-radius:12px; padding:24px; box-shadow:0 6px 24px rgba(0,0,0,.08); }
    .editor-header{ display:flex; justify-content:space-between; align-items:center; margin-bottom:18px; }
    .editor-body{ display:flex; flex-direction:column; gap:14px; }
    .grid{ display:grid; gap:14px; }
    .grid.two{ grid-template-columns:1fr 1fr; }
    .grid.three{ grid-template-columns:1fr 1fr 1fr; }
    label{ display:flex; flex-direction:column; gap:6px; font-size:13px; color:#374151; }
    span{ font-weight:600; }
    input, textarea{ width:100%; padding:10px 12px; border:1px solid #d1d5db; border-radius:8px; font:inherit; }
    textarea{ resize:vertical; }
    .checkline{ flex-direction:row; align-items:center; gap:10px; padding-top:26px; }
    .checkline input{ width:auto; }
    .field-builder{ border:1px solid #e5e7eb; border-radius:10px; padding:14px; background:#fafafa; }
    .field-builder__header{ display:flex; justify-content:space-between; align-items:center; margin-bottom:10px; font-weight:700; }
    .field-row{ display:grid; grid-template-columns: 2fr 1fr auto auto; gap:10px; align-items:center; margin-bottom:10px; }
    .req-toggle{ flex-direction:row; align-items:center; gap:8px; }
    .small{ font-size:16px; padding:4px 8px; }
    details{ border:1px solid #e5e7eb; border-radius:8px; padding:12px; background:#fafafa; }
    summary{ cursor:pointer; font-weight:700; margin-bottom:10px; }
    .actions{ display:flex; justify-content:flex-end; gap:10px; margin-top:8px; }
    .btn-primary,.btn-secondary,.btn-close{ border:none; border-radius:8px; cursor:pointer; }
    .btn-primary{ background:#2563eb; color:#fff; padding:10px 16px; }
    .btn-secondary{ background:#e5e7eb; color:#111827; padding:10px 16px; }
    .btn-close{ background:transparent; font-size:22px; padding:2px 8px; }
    .error{ color:#b91c1c; background:#fee2e2; padding:10px 12px; border-radius:8px; }
    .success{ color:#166534; background:#dcfce7; padding:10px 12px; border-radius:8px; }
  `]
})
export class QualifierEditorComponent implements OnChanges {
  @Input() qualifier: Qualifier | null = null;
  @Output() saved = new EventEmitter<void>();
  @Output() cancelled = new EventEmitter<void>();

  name = '';
  slug = '';
  systemPrompt = '';
  assistantStyle = 'friendly, concise, consultative';
  goalDefinition = '';
  trackedFields: TrackedField[] = [
    { name: 'intent', type: 'string', required: true },
    { name: 'timeline', type: 'string', required: false },
    { name: 'urgency', type: 'string', required: false },
    { name: 'budget', type: 'string', required: false },
    { name: 'location', type: 'string', required: false },
    { name: 'contact_email', type: 'string', required: false },
    { name: 'contact_phone', type: 'string', required: false },
    { name: 'human_request', type: 'boolean', required: false },
    { name: 'objections', type: 'array', required: false },
  ];
  confidenceThresholdsText = JSON.stringify({ overall_min_for_takeover: 0.7, field_min_for_fact_persistence: 0.6 }, null, 2);
  takeoverRulesText = JSON.stringify({ offer_on_explicit_human_request: true, offer_on_hot_band: true, offer_on_video_eligible: true }, null, 2);
  videoOfferRulesText = JSON.stringify({ enabled: true, requires_takeover_eligible: true, operator_can_offer_manually: true }, null, 2);
  scoringRulesText = JSON.stringify({ notes: 'Runtime heuristic + LLM extraction assisted scoring' }, null, 2);
  ragEnabled = false;
  maxClarifyingQuestions = 3;
  contactCapturePolicy = 'when_high_intent_or_explicit';
  hotMin = 80;
  warmMin = 50;
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
    this.confidenceThresholdsText = JSON.stringify(this.qualifier.confidence_thresholds || {}, null, 2);
    this.takeoverRulesText = JSON.stringify(this.qualifier.takeover_rules || {}, null, 2);
    this.videoOfferRulesText = JSON.stringify(this.qualifier.video_offer_rules || {}, null, 2);
    this.scoringRulesText = JSON.stringify(this.qualifier.scoring_rules || {}, null, 2);
    this.ragEnabled = !!this.qualifier.rag_enabled;
    this.maxClarifyingQuestions = this.qualifier.max_clarifying_questions ?? 3;
    this.contactCapturePolicy = this.qualifier.contact_capture_policy || 'when_high_intent_or_explicit';
    this.hotMin = this.qualifier.band_thresholds?.hot_min ?? 80;
    this.warmMin = this.qualifier.band_thresholds?.warm_min ?? 50;
    this.successMessage = '';
    this.errorMessage = '';
  }

  isValid(): boolean {
    return !!this.name.trim() && !!this.slug.trim() && !!this.systemPrompt.trim() && this.trackedFields.some(f => !!f.name.trim());
  }

  addField() {
    this.trackedFields = [...this.trackedFields, { name: '', type: 'string', required: false }];
  }

  removeField(index: number) {
    this.trackedFields = this.trackedFields.filter((_, i) => i !== index);
  }

  generatedFieldSchemaText(): string {
    return JSON.stringify(this.buildFieldSchema(), null, 2);
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

  private toTrackedFields(fieldSchema: Record<string, any>, requiredFields: string[]): TrackedField[] {
    const keys = Object.keys(fieldSchema || {});
    if (!keys.length) return [{ name: 'intent', type: 'string', required: true }];
    return keys.map((key) => ({
      name: key,
      type: (fieldSchema[key]?.type || 'string') as any,
      required: !!fieldSchema[key]?.required || requiredFields.includes(key),
    }));
  }

  save() {
    this.errorMessage = '';
    this.successMessage = '';
    let fieldSchema: any;
    let confidenceThresholds: any;
    let takeoverRules: any;
    let videoOfferRules: any;
    let scoringRules: any;

    try {
      fieldSchema = this.buildFieldSchema();
      confidenceThresholds = JSON.parse(this.confidenceThresholdsText || '{}');
      takeoverRules = JSON.parse(this.takeoverRulesText || '{}');
      videoOfferRules = JSON.parse(this.videoOfferRulesText || '{}');
      scoringRules = JSON.parse(this.scoringRulesText || '{}');
    } catch (e: any) {
      this.errorMessage = 'One of the JSON fields is invalid.';
      return;
    }

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
      version_notes: this.qualifier?.version_notes || 'Updated from dashboard editor'
    };

    this.saving = true;
    if (this.qualifier) {
      const payload: QualifierUpdate = basePayload;
      this.qualifiersService.updateQualifier(this.qualifier.id, payload).subscribe({
        next: () => {
          this.saving = false;
          this.successMessage = 'Qualifier saved.';
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
          this.successMessage = 'Qualifier created.';
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
