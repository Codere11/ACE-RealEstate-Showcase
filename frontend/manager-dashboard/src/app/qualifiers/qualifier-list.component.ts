import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Qualifier } from '../models/qualifier.model';
import { QualifiersService } from '../services/qualifiers.service';
import { QualifierEditorComponent } from './qualifier-editor.component';

@Component({
  selector: 'app-qualifier-list',
  standalone: true,
  imports: [CommonModule, QualifierEditorComponent],
  template: `
    <div class="qualifier-list" *ngIf="!editing">
      <div class="header">
        <div>
          <h1>AI Qualifiers</h1>
          <p>Create, tune, publish, and archive the active AI qualifier.</p>
        </div>
        <button class="btn-primary" (click)="createNew()">+ New Qualifier</button>
      </div>

      <div class="info-card" *ngIf="liveQualifierSlug">
        <strong>Live qualifier:</strong> {{ liveQualifierSlug }}
      </div>

      <div *ngIf="loading" class="empty">Loading qualifiers...</div>
      <div *ngIf="!loading && qualifiers.length === 0" class="empty">No qualifiers yet. Create one to enable AI qualification.</div>

      <table *ngIf="!loading && qualifiers.length > 0">
        <thead>
          <tr>
            <th>Name</th>
            <th>Status</th>
            <th>Version</th>
            <th>Updated</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          <tr *ngFor="let q of qualifiers">
            <td>
              <div class="name">{{ q.name }}</div>
              <div class="slug">{{ q.slug }}</div>
            </td>
            <td><span class="status" [class]="q.status">{{ q.status }}</span></td>
            <td>{{ q.version }}</td>
            <td>{{ q.updated_at | date:'short' }}</td>
            <td class="actions">
              <button class="btn-edit" (click)="edit(q)">Edit</button>
              <button class="btn-publish" *ngIf="q.status === 'draft' || q.status === 'archived'" (click)="publish(q)">Publish</button>
              <button class="btn-archive" *ngIf="q.status === 'live'" (click)="archive(q)">Archive</button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <app-qualifier-editor
      *ngIf="editing"
      [qualifier]="selected"
      (saved)="onSaved()"
      (cancelled)="cancelEdit()"
    ></app-qualifier-editor>
  `,
  styles: [`
    .qualifier-list{ background:#fff; padding:28px; border-radius:12px; }
    .header{ display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:18px; gap:16px; }
    .header h1{ margin:0 0 4px; }
    .header p{ margin:0; color:#6b7280; }
    .info-card{ background:#eff6ff; color:#1d4ed8; border-radius:10px; padding:12px 14px; margin-bottom:16px; }
    .empty{ background:#f9fafb; border:1px dashed #d1d5db; padding:24px; border-radius:10px; color:#6b7280; }
    table{ width:100%; border-collapse:collapse; }
    th,td{ padding:12px; border-bottom:1px solid #e5e7eb; text-align:left; }
    th{ background:#f9fafb; color:#4b5563; }
    .name{ font-weight:700; color:#111827; }
    .slug{ font-size:12px; color:#6b7280; margin-top:4px; }
    .status{ padding:4px 10px; border-radius:999px; font-size:12px; text-transform:capitalize; font-weight:700; }
    .status.draft{ background:#fef3c7; color:#92400e; }
    .status.live{ background:#dcfce7; color:#166534; }
    .status.archived{ background:#e5e7eb; color:#374151; }
    .actions{ display:flex; gap:8px; flex-wrap:wrap; }
    .btn-primary,.btn-edit,.btn-publish,.btn-archive{ border:none; border-radius:8px; padding:8px 12px; cursor:pointer; font-weight:600; }
    .btn-primary,.btn-edit{ background:#2563eb; color:#fff; }
    .btn-publish{ background:#16a34a; color:#fff; }
    .btn-archive{ background:#6b7280; color:#fff; }
  `]
})
export class QualifierListComponent implements OnInit {
  qualifiers: Qualifier[] = [];
  loading = true;
  editing = false;
  selected: Qualifier | null = null;
  liveQualifierSlug = '';

  constructor(private qualifiersService: QualifiersService) {}

  ngOnInit(): void {
    this.load();
  }

  load() {
    this.loading = true;
    this.qualifiersService.listQualifiers().subscribe({
      next: (items) => {
        this.qualifiers = items;
        this.liveQualifierSlug = items.find(i => i.status === 'live')?.slug || '';
        this.loading = false;
      },
      error: (err) => {
        console.error('Failed to load qualifiers', err);
        this.loading = false;
      }
    });
  }

  createNew() {
    this.selected = null;
    this.editing = true;
  }

  edit(q: Qualifier) {
    this.selected = q;
    this.editing = true;
  }

  publish(q: Qualifier) {
    this.qualifiersService.publishQualifier(q.id).subscribe({ next: () => this.load(), error: err => alert(err?.error?.detail || 'Failed to publish qualifier') });
  }

  archive(q: Qualifier) {
    this.qualifiersService.archiveQualifier(q.id).subscribe({ next: () => this.load(), error: err => alert(err?.error?.detail || 'Failed to archive qualifier') });
  }

  onSaved() {
    this.editing = false;
    this.selected = null;
    this.load();
  }

  cancelEdit() {
    this.editing = false;
    this.selected = null;
  }
}
