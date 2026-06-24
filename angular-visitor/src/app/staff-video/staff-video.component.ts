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

  // 'prompt' = consent dialog shown | 'connecting' = user accepted, connecting | 'connected' = live | 'idle' = nothing
  readonly consentState = signal<'prompt' | 'connecting' | 'connected' | 'idle'>('idle');
  readonly managerName = signal('');
  readonly selfCameraOn = signal(false);
  readonly selfMicOn = signal(false);

  private room: Room | null = null;
  private localVideo: LocalVideoTrack | null = null;
  private localAudio: LocalAudioTrack | null = null;
  private pollTimer: any = null;
  private disposed = false;

  constructor() {
    // Start polling immediately — don't rely on monkey-patch timing
    this.startPolling();

    // Also listen via staffState for faster reaction
    const orig = this.salon.staffState.set.bind(this.salon.staffState);
    this.salon.staffState.set = (v: any) => {
      orig(v);
      if (v === 'connected' && this.consentState() === 'idle') {
        this.zone.run(() => this.checkSession());
      } else if (v === 'idle') {
        this.zone.run(() => this.disconnect());
      }
    };
  }

  private startPolling() {
    if (this.pollTimer) return;
    this.checkSession();
    this.pollTimer = setInterval(() => this.checkSession(), 3000);
  }

  private stopPolling() {
    if (this.pollTimer) { clearInterval(this.pollTimer); this.pollTimer = null; }
  }

  private async checkSession() {
    if (this.disposed) return;
    // Only poll when idle (no prompt up, no connection active)
    if (this.consentState() !== 'idle') return;
    const sid = (this.salon as any).sid;
    if (!sid) return;
    try {
      const slug = this.getTenantSlug();
      const r = await fetch(`/api/public/organizations/${slug}/live-session?sid=${sid}`);
      if (!r.ok) return;
      const data = await r.json();
      if (data.status === 'live' && data.token && this.consentState() === 'idle') {
        this.managerName.set(data.managerDisplayName || 'Ekipa');
        // Store token for accept()
        (this as any)._pendingToken = data.token;
        (this as any)._pendingWsUrl = data.wsUrl;
        this.stopPolling();
        this.consentState.set('prompt');
      }
    } catch {}
  }

  async accept() {
    const token = (this as any)._pendingToken;
    const wsUrl = (this as any)._pendingWsUrl;
    if (!token || !wsUrl) return;
    (this as any)._pendingToken = null;
    (this as any)._pendingWsUrl = null;

    this.consentState.set('connecting');
    this.selfMicOn.set(true);
    this.selfCameraOn.set(false);

    try {
      await this.joinRoom(wsUrl, token);
      this.consentState.set('connected');
    } catch (e) {
      console.error('LiveKit join failed:', e);
      this.disconnect();
      this.startPolling();
    }
  }

  decline() {
    this.disconnect();
    this.startPolling();
    const sid = (this.salon as any).sid;
    if (sid) {
      fetch(`/api/public/organizations/${this.getTenantSlug()}/live-session/decline`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ sid }),
      }).catch(() => {});
    }
  }

  hangup() {
    this.disconnect();
    this.startPolling();
    const sid = (this.salon as any).sid;
    if (sid) {
      fetch(`/api/public/organizations/${this.getTenantSlug()}/live-session/hangup`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ sid }),
      }).catch(() => {});
    }
  }

  toggleMic() {
    if (!this.localAudio) return;
    const next = !this.selfMicOn();
    this.selfMicOn.set(next);
    next ? this.localAudio.unmute() : this.localAudio.mute();
  }

  async toggleCamera() {
    const next = !this.selfCameraOn();
    this.selfCameraOn.set(next);
    if (next) {
      await this.enableLocalVideo();
    } else if (this.localVideo) {
      this.localVideo.stop();
      await this.room?.localParticipant.unpublishTrack(this.localVideo);
      this.localVideo = null;
      const pel = document.getElementById('ace-local-video') as HTMLVideoElement | null;
      if (pel) pel.srcObject = null;
    }
  }

  private async enableLocalVideo() {
    if (!this.room || this.localVideo) return;
    try {
      this.localVideo = await createLocalVideoTrack({ facingMode: 'user' });
      await this.room.localParticipant.publishTrack(this.localVideo);
      const el = document.getElementById('ace-local-video') as HTMLVideoElement | null;
      if (el) this.localVideo.attach(el);
    } catch (e) {
      console.error('Failed to enable camera:', e);
      this.selfCameraOn.set(false);
    }
  }

  private async joinRoom(wsUrl: string, token: string) {
    this.disconnectRoom();

    this.room = new Room({ adaptiveStream: true, dynacast: true });

    this.room.on(RoomEvent.TrackSubscribed, (track: RemoteTrack, _pub: RemoteTrackPublication, _participant: any) => {
      this.zone.run(() => {
        if (track.kind === Track.Kind.Video) {
          const el = document.getElementById('ace-remote-video') as HTMLVideoElement | null;
          if (el) {
            track.attach(el);
            el.style.opacity = '1';
          }
        }
        if (track.kind === Track.Kind.Audio) {
          track.attach();
        }
      });
    });

    this.room.on(RoomEvent.TrackUnsubscribed, (track: RemoteTrack) => {
      if (track.kind === Track.Kind.Video) {
        const el = document.getElementById('ace-remote-video') as HTMLVideoElement | null;
        if (el) el.style.opacity = '0';
      }
    });

    this.room.on(RoomEvent.Disconnected, () => {
      this.zone.run(() => {
        if (!this.disposed) { this.disconnect(); this.startPolling(); }
      });
    });

    this.room.on(RoomEvent.ConnectionStateChanged, (state: ConnectionState) => {
      if (state === ConnectionState.Disconnected && !this.disposed) {
        this.zone.run(() => { this.disconnect(); this.startPolling(); });
      }
    });

    await this.room.connect(wsUrl, token);

    // Create local audio (muted)
    try {
      this.localAudio = await createLocalAudioTrack();
      this.localAudio.mute();
      await this.room.localParticipant.publishTrack(this.localAudio);
      this.selfMicOn.set(false);
    } catch (e) {
      console.error('Failed to create local audio:', e);
    }
  }

  private disconnectRoom() {
    try { this.localVideo?.stop(); } catch {}
    try { this.localAudio?.stop(); } catch {}
    try { this.room?.disconnect(); } catch {}
    this.localVideo = null;
    this.localAudio = null;
    this.room = null;
  }

  private disconnect() {
    this.disconnectRoom();
    this.consentState.set('idle');
    this.selfCameraOn.set(false);
    this.selfMicOn.set(false);
  }

  ngOnDestroy() {
    this.disposed = true;
    this.stopPolling();
    this.disconnectRoom();
  }

  private getTenantSlug(): string {
    if (typeof window !== 'undefined') {
      const p = new URLSearchParams(window.location.search).get('org'); if (p) return p;
      const seg = window.location.pathname.replace(/^\/+/, '').split('/')[0]; if (seg) return seg;
    }
    return 'demo';
  }
}
