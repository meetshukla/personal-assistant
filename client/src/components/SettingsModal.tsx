"use client";
import { useCallback, useEffect, useMemo, useState } from 'react';

export type Settings = {};

export function useSettings() {
  const [settings, setSettings] = useState<Settings>({});

  const persist = useCallback((s: Settings) => {
    setSettings(s);
  }, []);

  return { settings, setSettings: persist } as const;
}

function coerceEmailFrom(value: unknown): string | null {
  if (typeof value === 'string' && value.includes('@')) {
    return value;
  }
  if (value && typeof value === 'object') {
    const candidate =
      (value as any).emailAddress ??
      (value as any).email ??
      (value as any).value ??
      (value as any).address;
    if (typeof candidate === 'string' && candidate.includes('@')) {
      return candidate;
    }
  }
  return null;
}

function deriveEmailFromPayload(payload: any): string {
  if (!payload) return '';
  const profileSlice = payload?.profile;
  const candidateObjects: any[] = [];

  if (profileSlice && typeof profileSlice === 'object') {
    candidateObjects.push(profileSlice);
    if ((profileSlice as any).response_data && typeof (profileSlice as any).response_data === 'object') {
      candidateObjects.push((profileSlice as any).response_data);
    }
    if (Array.isArray((profileSlice as any).items)) {
      for (const entry of (profileSlice as any).items as any[]) {
        if (entry && typeof entry === 'object') {
          if (typeof entry.data === 'object') candidateObjects.push(entry.data);
          if (typeof entry.response_data === 'object') candidateObjects.push(entry.response_data);
          if (typeof entry.profile === 'object') candidateObjects.push(entry.profile);
        }
      }
    }
  }

  const directCandidates = [payload?.email];

  for (const obj of candidateObjects) {
    if (!obj || typeof obj !== 'object') continue;
    directCandidates.push(
      obj?.email,
      obj?.email_address,
      obj?.emailAddress,
      obj?.profile?.email,
      obj?.profile?.emailAddress,
      obj?.profile?.email_address,
      obj?.user?.email,
      obj?.user?.emailAddress,
      obj?.user?.email_address,
      obj?.data?.email,
      obj?.data?.emailAddress,
      obj?.data?.email_address,
    );
    const emailAddresses = (obj as any).emailAddresses;
    if (Array.isArray(emailAddresses)) {
      for (const entry of emailAddresses) {
        const email = coerceEmailFrom(entry) ?? coerceEmailFrom((entry as any)?.value);
        if (email) return email;
      }
    }
  }

  for (const candidate of directCandidates) {
    const email = coerceEmailFrom(candidate);
    if (email) return email;
  }

  return '';
}

export default function SettingsModal({
  open,
  onClose,
  settings,
  onSave,
}: {
  open: boolean;
  onClose: () => void;
  settings: Settings;
  onSave: (s: Settings) => void;
}) {
  const [connectingGmail, setConnectingGmail] = useState(false);
  const [isRefreshingGmail, setIsRefreshingGmail] = useState(false);
  const [isDisconnecting, setIsDisconnecting] = useState(false);
  const [gmailStatusMessage, setGmailStatusMessage] = useState('');
  const [gmailConnected, setGmailConnected] = useState(false);
  const [gmailEmail, setGmailEmail] = useState('');
  const [gmailConnId, setGmailConnId] = useState('');
  const [gmailProfile, setGmailProfile] = useState<Record<string, unknown> | null>(null);
  const [pollIntervalRef, setPollIntervalRef] = useState<NodeJS.Timeout | null>(null);

  const readStoredUserId = useCallback(() => {
    if (typeof window === 'undefined') return '';
    try {
      return localStorage.getItem('personal_assistant_user_id') || '';
    } catch {
      return '';
    }
  }, []);

  const ensureUserId = useCallback(() => {
    if (typeof window === 'undefined') {
      return `web-${Math.random().toString(36).slice(2)}`;
    }
    try {
      const existing = localStorage.getItem('personal_assistant_user_id');
      if (existing) {
        console.log('Using existing user ID:', existing);
        return existing;
      }
      const cryptoObj = (globalThis as { crypto?: Crypto }).crypto;
      const randomPart =
        cryptoObj && typeof cryptoObj.randomUUID === 'function'
          ? cryptoObj.randomUUID().replace(/-/g, '')
          : Math.random().toString(36).slice(2);
      const generated = `web-${randomPart}`;
      console.log('Generated new user ID:', generated);
      localStorage.setItem('personal_assistant_user_id', generated);
      return generated;
    } catch {
      return `web-${Math.random().toString(36).slice(2)}`;
    }
  }, []);

  const readStoredConnectionRequestId = useCallback(() => {
    if (gmailConnId) return gmailConnId;
    if (typeof window === 'undefined') return '';
    try {
      return localStorage.getItem('gmail_connection_request_id') || '';
    } catch {
      return '';
    }
  }, [gmailConnId]);

  useEffect(() => {
    try {
      const savedConnected = localStorage.getItem('gmail_connected') === 'true';
      const savedConnId = localStorage.getItem('gmail_connection_request_id') || '';
      const savedEmail = localStorage.getItem('gmail_email') || '';
      setGmailConnected(savedConnected);
      setGmailConnId(savedConnId);
      setGmailEmail(savedEmail);
      if (savedConnected && savedEmail) {
        setGmailStatusMessage(`Connected as ${savedEmail}`);
      }
    } catch {}
  }, []);

  const gmailProfileDetails = useMemo(() => {
    if (!gmailProfile) return [] as { label: string; value: string }[];
    const details: { label: string; value: string }[] = [];
    const messagesTotal = (gmailProfile as any)?.messagesTotal;
    if (typeof messagesTotal === 'number') {
      details.push({ label: 'Messages', value: messagesTotal.toLocaleString() });
    }
    const threadsTotal = (gmailProfile as any)?.threadsTotal;
    if (typeof threadsTotal === 'number') {
      details.push({ label: 'Threads', value: threadsTotal.toLocaleString() });
    }
    const historyId = (gmailProfile as any)?.historyId ?? (gmailProfile as any)?.historyID;
    if (historyId !== undefined && historyId !== null && historyId !== '') {
      details.push({ label: 'History ID', value: String(historyId) });
    }
    return details;
  }, [gmailProfile]);

  const handleConnectGmail = useCallback(async () => {
    try {
      setConnectingGmail(true);
      setGmailStatusMessage('');
      const userId = ensureUserId();
      const resp = await fetch('http://localhost:8001/api/gmail/connect', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ userId }),
      });
      const data = await resp.json().catch(() => ({}));
      if (!resp.ok || !data?.ok) {
        const msg = data?.error || `Failed (${resp.status})`;
        setGmailStatusMessage(msg);
        return;
      }
      const url = data?.redirect_url;
      const connId = data?.connection_request_id || '';
      if (connId) {
        setGmailConnId(connId);
        try {
          localStorage.setItem('gmail_connection_request_id', connId);
        } catch {}
      }
      setGmailConnected(false);
      setGmailEmail('');
      setGmailProfile(null);
      if (url) {
        window.open(url, '_blank', 'noopener');
        setGmailStatusMessage('Gmail authorization opened in a new tab. Waiting for completion...');

        // Clear any existing polling interval
        if (pollIntervalRef) {
          clearInterval(pollIntervalRef);
        }

        // Start polling for connection status every 3 seconds
        let pollCount = 0;
        const maxPolls = 40; // 2 minutes maximum
        console.log('Starting polling with userId:', userId, 'connId:', connId);
        const pollInterval = setInterval(async () => {
          pollCount++;
          console.log(`Poll ${pollCount}/${maxPolls} - checking status for userId:`, userId);
          try {
            const statusResp = await fetch('http://localhost:8001/api/gmail/status', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ userId, connectionRequestId: connId }),
            });
            const statusData = await statusResp.json().catch(() => ({}));
            console.log('Poll response:', statusData);

            if (statusData?.connected) {
              // Connection successful!
              console.log('Connection detected! Stopping polling');
              clearInterval(pollInterval);
              setPollIntervalRef(null);

              // Store the user ID that successfully connected
              try {
                localStorage.setItem('personal_assistant_user_id', userId);
                localStorage.setItem('gmail_connection_request_id', connId);
                localStorage.setItem('gmail_connected', 'true');
                localStorage.setItem('gmail_email', statusData?.email || '');
                console.log('Stored connection data in localStorage');
              } catch {}

              await refreshGmailStatus(); // Update UI with full status
              setGmailStatusMessage('Gmail connected successfully!');
            } else if (pollCount >= maxPolls) {
              // Timeout
              clearInterval(pollInterval);
              setPollIntervalRef(null);
              setGmailStatusMessage('Authorization timed out. Please try connecting again or press "Refresh status".');
            }
          } catch {
            // Continue polling on error
          }
        }, 3000);

        setPollIntervalRef(pollInterval);
      } else {
        setGmailStatusMessage('Connection initiated. Refresh status once authorization completes.');
      }
    } catch (e: any) {
      setGmailStatusMessage(e?.message || 'Failed to connect Gmail');
    } finally {
      setConnectingGmail(false);
    }
  }, [ensureUserId]);

  const refreshGmailStatus = useCallback(async () => {
    let userId = readStoredUserId();
    const connectionRequestId = readStoredConnectionRequestId();
    console.log('refreshGmailStatus - stored userId:', userId, 'connectionRequestId:', connectionRequestId);

    // If no stored user ID, ensure we have one
    if (!userId) {
      userId = ensureUserId();
      console.log('refreshGmailStatus - ensured userId:', userId);
    }

    if (!userId && !connectionRequestId) {
      console.log('refreshGmailStatus - no userId or connectionRequestId, showing connect message');
      setGmailConnected(false);
      setGmailProfile(null);
      setGmailEmail('');
      setGmailStatusMessage('Connect Gmail to get started.');
      return;
    }

    try {
      setIsRefreshingGmail(true);
      setGmailStatusMessage('Refreshing Gmail status…');
      console.log('refreshGmailStatus - making API call with:', { userId, connectionRequestId });
      const resp = await fetch('http://localhost:8001/api/gmail/status', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ userId, connectionRequestId }),
      });
      const data = await resp.json().catch(() => ({}));
      console.log('refreshGmailStatus - API response:', data);

      if (!resp.ok || !data?.ok) {
        const message = data?.error || `Failed (${resp.status})`;
        setGmailConnected(false);
        setGmailProfile(null);
        setGmailEmail('');
        setGmailStatusMessage(message);
        return;
      }

      if (!gmailConnId && connectionRequestId) {
        setGmailConnId(connectionRequestId);
      }

      const profileData = data?.profile && typeof data.profile === 'object' ? (data.profile as Record<string, unknown>) : null;
      setGmailProfile(profileData);

      const derivedEmail = deriveEmailFromPayload({ email: data?.email, profile: profileData });
      const email = derivedEmail || (typeof data?.email === 'string' ? data.email : '');
      const connected = Boolean(data?.connected);

      setGmailConnected(connected);
      setGmailEmail(email);

      if (connected) {
        const source = typeof data?.profile_source === 'string' ? data.profile_source : '';
        const sourceNote = source === 'fetched' ? 'Verified moments ago.' : source === 'cache' ? 'Loaded from cache.' : '';
        const message = email ? `Connected as ${email}` : 'Gmail connected.';
        setGmailStatusMessage(sourceNote ? `${message} ${sourceNote}` : message);
        try {
          localStorage.setItem('gmail_connected', 'true');
          if (email) localStorage.setItem('gmail_email', email);
          if (typeof data?.user_id === 'string' && data.user_id) {
            localStorage.setItem('personal_assistant_user_id', data.user_id);
          }
        } catch {}
      } else {
        const statusText = typeof data?.status === 'string' && data.status && data.status !== 'UNKNOWN'
          ? `Status: ${data.status}`
          : 'Not connected yet.';
        setGmailStatusMessage(statusText);
        try {
          localStorage.removeItem('gmail_connected');
          localStorage.removeItem('gmail_email');
        } catch {}
      }
    } catch (e: any) {
      setGmailConnected(false);
      setGmailProfile(null);
      setGmailEmail('');
      setGmailStatusMessage(e?.message || 'Failed to check Gmail status');
    } finally {
      setIsRefreshingGmail(false);
    }
  }, [gmailConnId, readStoredConnectionRequestId, readStoredUserId, ensureUserId]);

  const handleDisconnectGmail = useCallback(async () => {
    if (typeof window !== 'undefined') {
      const proceed = window.confirm(
        gmailEmail
          ? `Disconnect ${gmailEmail} from Personal Assistant?`
          : 'Disconnect Gmail from Personal Assistant?'
      );
      if (!proceed) return;
    }

    try {
      setIsDisconnecting(true);
      setGmailStatusMessage('Disconnecting Gmail…');

      // Stop any polling
      if (pollIntervalRef) {
        clearInterval(pollIntervalRef);
        setPollIntervalRef(null);
      }

      const userId = readStoredUserId();
      const connectionRequestId = readStoredConnectionRequestId();
      const resp = await fetch('http://localhost:8001/api/gmail/disconnect', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ userId, connectionRequestId }),
      });
      const data = await resp.json().catch(() => ({}));

      if (!resp.ok || !data?.ok) {
        const message = data?.error || `Failed (${resp.status})`;
        setGmailStatusMessage(message);
        return;
      }

      // Reset all Gmail state
      setGmailConnected(false);
      setGmailEmail('');
      setGmailProfile(null);
      setGmailConnId('');
      setGmailStatusMessage('Gmail disconnected. You can now connect a different account.');

      // Clear all stored data and generate new user ID for clean switching
      try {
        localStorage.removeItem('gmail_connected');
        localStorage.removeItem('gmail_email');
        localStorage.removeItem('gmail_connection_request_id');
        localStorage.removeItem('personal_assistant_user_id'); // Clear to allow new email connection
      } catch {}
    } catch (e: any) {
      setGmailStatusMessage(e?.message || 'Failed to disconnect Gmail');
    } finally {
      setIsDisconnecting(false);
    }
  }, [readStoredConnectionRequestId, readStoredUserId, gmailEmail, pollIntervalRef]);


  useEffect(() => {
    if (!open) return;
    void refreshGmailStatus();
  }, [open, refreshGmailStatus]);

  // Cleanup polling interval on unmount
  useEffect(() => {
    return () => {
      if (pollIntervalRef) {
        clearInterval(pollIntervalRef);
      }
    };
  }, [pollIntervalRef]);

  if (!open) return null;

  const connectButtonLabel = connectingGmail ? 'Opening…' : gmailConnected ? 'Reconnect' : 'Connect Gmail';
  const refreshButtonLabel = isRefreshingGmail ? 'Refreshing…' : 'Refresh status';
  const disconnectButtonLabel = isDisconnecting ? 'Disconnecting…' : 'Disconnect';

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
      <div className="bg-card border border-border/40 rounded-2xl w-full max-w-lg shadow-2xl shadow-black/20">
        {/* Header */}
        <div className="p-6 border-b border-border/40">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-xl font-semibold text-foreground">Settings</h2>
              <p className="text-sm text-muted-foreground mt-1">Manage your integrations and preferences</p>
            </div>
            <button
              onClick={onClose}
              className="w-8 h-8 flex items-center justify-center rounded-lg text-muted-foreground hover:text-foreground hover:bg-muted/50 transition-colors"
              aria-label="Close"
            >
              ✕
            </button>
          </div>
        </div>

        {/* Content */}
        <div className="p-6 space-y-6">
          {/* Gmail Section */}
          <div>
            <div className="flex items-center space-x-2 mb-4">
              <div className="w-8 h-8 bg-gradient-to-br from-red-500 to-orange-600 rounded-lg flex items-center justify-center">
                <span className="text-white text-sm font-bold">G</span>
              </div>
              <div>
                <h3 className="font-medium text-foreground">Gmail Integration</h3>
                <p className="text-xs text-muted-foreground">Connect your Gmail account to manage emails</p>
              </div>
            </div>

            <div className="border border-border/40 rounded-xl p-4 bg-muted/30">
              {gmailConnected ? (
                <div className="space-y-4">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center space-x-2">
                      <div className="w-2 h-2 bg-green-500 rounded-full"></div>
                      <span className="text-sm font-medium text-foreground">Connected</span>
                    </div>
                    <div className="text-xs text-muted-foreground font-mono bg-muted/60 px-2 py-1 rounded-md">
                      {gmailEmail}
                    </div>
                  </div>

                  {gmailProfileDetails.length > 0 && (
                    <div className="grid grid-cols-3 gap-3">
                      {gmailProfileDetails.map((item) => (
                        <div key={item.label} className="text-center bg-card/50 rounded-lg p-3 border border-border/30">
                          <div className="font-semibold text-foreground text-sm">{item.value}</div>
                          <div className="text-xs text-muted-foreground mt-1">{item.label}</div>
                        </div>
                      ))}
                    </div>
                  )}

                  {gmailStatusMessage && (
                    <div className="text-xs text-muted-foreground bg-muted/60 p-3 rounded-lg border border-border/30">
                      {gmailStatusMessage}
                    </div>
                  )}
                </div>
              ) : (
                <div className="text-center py-6">
                  <div className="w-12 h-12 bg-muted/60 rounded-full flex items-center justify-center mx-auto mb-3">
                    <span className="text-muted-foreground text-xl">📧</span>
                  </div>
                  <div className="text-sm text-muted-foreground mb-2">Not connected</div>
                  {gmailStatusMessage && (
                    <div className="text-xs text-muted-foreground/70 max-w-xs mx-auto">
                      {gmailStatusMessage}
                    </div>
                  )}
                </div>
              )}

              <div className="flex flex-wrap gap-2 mt-4 pt-4 border-t border-border/30">
                <button
                  type="button"
                  className="px-4 py-2 text-sm bg-primary text-primary-foreground rounded-lg hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed transition-colors font-medium"
                  onClick={handleConnectGmail}
                  disabled={connectingGmail || isRefreshingGmail || isDisconnecting}
                >
                  {connectButtonLabel}
                </button>

                <button
                  type="button"
                  className="px-4 py-2 text-sm border border-border/60 text-foreground rounded-lg hover:bg-muted/50 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                  onClick={refreshGmailStatus}
                  disabled={isRefreshingGmail || connectingGmail}
                >
                  {refreshButtonLabel}
                </button>

                {gmailConnected && (
                  <button
                    type="button"
                    className="px-4 py-2 text-sm border border-destructive/60 text-destructive rounded-lg hover:bg-destructive/10 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                    onClick={handleDisconnectGmail}
                    disabled={isDisconnecting || connectingGmail}
                  >
                    {disconnectButtonLabel}
                  </button>
                )}
              </div>
            </div>
          </div>

          {/* Future Integrations Placeholder */}
          <div className="border border-dashed border-border/40 rounded-xl p-6 text-center">
            <div className="text-muted-foreground text-sm">
              <div className="text-2xl mb-2">🔗</div>
              More integrations coming soon...
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="p-6 border-t border-border/40 flex justify-end">
          <button
            onClick={onClose}
            className="px-6 py-2 text-sm bg-muted/60 text-foreground rounded-lg hover:bg-muted/80 transition-colors"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}