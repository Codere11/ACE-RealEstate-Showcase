import { Component, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';

@Component({
  standalone: true,
  imports: [FormsModule],
  template: `
    <div style="max-width:400px;margin:100px auto;font-family:Inter,sans-serif;color:#e2e8f0;background:#0f172a;padding:32px;border-radius:16px;">
      <h1 style="margin:0 0 24px;text-align:center;">ACE Reception</h1>
      @if (error()) { <div style="color:#fca5a5;margin-bottom:12px;">{{ error() }}</div> }
      <div style="display:grid;gap:12px;">
        <input [(ngModel)]="username" placeholder="Username" style="padding:12px;border-radius:8px;border:1px solid #334;background:#1e293b;color:white;">
        <input [(ngModel)]="password" type="password" placeholder="Password" style="padding:12px;border-radius:8px;border:1px solid #334;background:#1e293b;color:white;" (keyup.enter)="login()">
        <button (click)="login()" style="padding:12px;border-radius:8px;border:none;background:linear-gradient(135deg,#93c5fd,#7ef0c7);color:#07111f;font-weight:700;cursor:pointer;">Login</button>
      </div>
    </div>
  `
})
export class LoginComponent {
  username = ''; password = ''; error = signal('');
  constructor(private router: Router) {}

  async login() {
    this.error.set('');
    try {
      const form = new URLSearchParams();
      form.set('username', this.username);
      form.set('password', this.password);
      const r = await fetch('/login', { method: 'POST', body: form });
      if (!r.ok) { this.error.set('Invalid credentials'); return; }
      const data = await r.json();
      localStorage.setItem('ace_token', data.token);
      if (data.role === 'PLATFORM_ADMIN') this.router.navigate(['/admin']);
      else this.router.navigate(['/demo/dashboard']);
    } catch { this.error.set('Connection failed'); }
  }
}
