import { Component, inject, OnDestroy, signal, NgZone } from '@angular/core';
import { SalonService } from '../services/salon.service';
import { Room, RoomEvent, RemoteTrack, RemoteTrackPublication, Track, ConnectionState, LocalVideoTrack, LocalAudioTrack, createLocalVideoTrack, createLocalAudioTrack } from 'livekit-client';

@Component({
  selector: 'app-staff-video',
  standalone: true,
  templateUrl: './staff-video.component.html',
  styleUrls: ['./staff-video.component.scss'],
})
export class StaffVideoComponent implements OnDestroy {
  readonly salon = inject(SalonService);
  private zone = inject(NgZone);

  readonly consentState = signal<'prompt' | 'connecting' | 'connected' | 'idle'>('idle');
  readonly managerName = signal('');
  readonly selfCameraOn = signal(false);
  readonly selfMicOn = signal(false);
  readonly isMinimized = signal(false);

  private room: Room | null = null;
  private localVideo: LocalVideoTrack | null = null;
  private localAudio: LocalAudioTrack | null = null;
  private pollTimer: any = null;
  private disposed = false;

  constructor() {
    this.startPolling();

    const orig = this.salon.staffState.set.bind(this.salon.staffState);
    this.salon.staffState.set = (v: any) => {
      orig(v);
      if (v === 'connected' && this.consentState() === 'idle') {
        this.zone.run(() => this.checkSession());
      } else if (v === 'idle') {
        this.zone.run(() => this.hangup());
      }
    };
  }

  private startPolling() {
    if (this.pollTimer) return;
    this.checkSession();
    this.pollTimer = setInterval(() => this.checkSession(), 3000);
  }

  private stopPolling() { if (this.pollTimer) { clearInterval(this.pollTimer); this.pollTimer = null; } }

  private async checkSession() {
    if (this.disposed || this.consentState() !== 'idle') return;
    const sid = (this.salon as any).sid;
    if (!sid) return;
    try {
      const slug = this.getTenantSlug();
      const r = await fetch(`/api/public/organizations/${slug}/live-session?sid=${sid}`);
      if (!r.ok) return;
      const data = await r.json();
      if (data.status === 'live' && data.token && this.consentState() === 'idle') {
        this.managerName.set(data.managerDisplayName || 'Ekipa');
        (this as any)._pt = data.token; (this as any)._pw = data.wsUrl;
        this.stopPolling(); this.consentState.set('prompt');
      }
    } catch {}
  }

  async accept() {
    const t = (this as any)._pt; const w = (this as any)._pw;
    if (!t || !w) return; (this as any)._pt = null; (this as any)._pw = null;
    this.consentState.set('connecting'); this.selfMicOn.set(true); this.selfCameraOn.set(false); this.isMinimized.set(false);
    try { await this.joinRoom(w, t); this.consentState.set('connected'); }
    catch (e) { console.error(e); this.disconnect(); this.startPolling(); }
  }

  decline() { this.disconnect(); this.startPolling(); }

  hangup() {
    this.disconnect(); this.startPolling();
    const sid = (this.salon as any).sid;
    if (sid) fetch(`/api/public/organizations/${this.getTenantSlug()}/live-session/hangup`, { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({sid}) }).catch(()=>{});
  }

  toggleMic() {
    if (!this.localAudio) return;
    if (this.selfMicOn()) { this.localAudio.mute(); this.selfMicOn.set(false); }
    else { this.localAudio.unmute(); this.selfMicOn.set(true); }
  }

  async toggleCamera() {
    if (this.selfCameraOn()) {
      if (this.localVideo) { this.localVideo.stop(); await this.room?.localParticipant.unpublishTrack(this.localVideo); this.localVideo = null; }
      this.selfCameraOn.set(false);
      const el = document.getElementById('ace-local-video') as HTMLVideoElement|null;
      if (el) el.style.display = 'none';
    } else {
      this.selfCameraOn.set(true);
      await this.enableLocalVideo();
    }
  }

  private async enableLocalVideo() {
    if (!this.room || this.localVideo) return;
    try {
      this.localVideo = await createLocalVideoTrack({ facingMode:'user' });
      await this.room.localParticipant.publishTrack(this.localVideo);
      const el = document.getElementById('ace-local-video') as HTMLVideoElement|null;
      if (el) { el.style.display = 'block'; this.localVideo.attach(el); }
    } catch (e) { console.error(e); this.selfCameraOn.set(false); }
  }

  private async joinRoom(wsUrl: string, token: string) {
    this.disconnectRoom();
    this.room = new Room({ adaptiveStream:true, dynacast:true });

    this.room.on(RoomEvent.TrackSubscribed, (track: RemoteTrack) => {
      this.zone.run(() => {
        if (track.kind === Track.Kind.Video) {
          const el = document.getElementById('ace-remote-video') as HTMLVideoElement|null;
          if (el) { track.attach(el); el.style.opacity = '1'; }
        }
        if (track.kind === Track.Kind.Audio) { track.attach(); }
      });
    });

    this.room.on(RoomEvent.TrackUnsubscribed, (track: RemoteTrack) => {
      if (track.kind === Track.Kind.Video) {
        const el = document.getElementById('ace-remote-video') as HTMLVideoElement|null;
        if (el) el.style.opacity = '0';
      }
    });

    this.room.on(RoomEvent.Disconnected, () => { if (!this.disposed) { this.zone.run(() => { this.disconnect(); this.startPolling(); }); } });
    this.room.on(RoomEvent.ConnectionStateChanged, (s: ConnectionState) => { if (s === ConnectionState.Disconnected && !this.disposed) { this.zone.run(() => { this.disconnect(); this.startPolling(); }); } });

    await this.room.connect(wsUrl, token);

    try {
      this.localAudio = await createLocalAudioTrack(); this.localAudio.mute();
      await this.room.localParticipant.publishTrack(this.localAudio);
      this.selfMicOn.set(false);
    } catch (e) { console.error(e); }
  }

  private disconnectRoom() {
    try { this.localVideo?.stop(); } catch {}
    try { this.localAudio?.stop(); } catch {}
    try { this.room?.disconnect(); } catch {}
    this.localVideo = null; this.localAudio = null; this.room = null;
  }

  private disconnect() {
    this.disconnectRoom();
    this.consentState.set('idle'); this.selfCameraOn.set(false); this.selfMicOn.set(false);
  }

  ngOnDestroy() { this.disposed = true; this.stopPolling(); this.disconnectRoom(); }

  private getTenantSlug(): string {
    if (typeof window !== 'undefined') {
      const p = new URLSearchParams(window.location.search).get('org'); if (p) return p;
      const seg = window.location.pathname.replace(/^\/+/, '').split('/')[0]; if (seg) return seg;
    }
    return 'demo';
  }
}
