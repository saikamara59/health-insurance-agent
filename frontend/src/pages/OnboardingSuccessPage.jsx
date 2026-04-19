import { useState, useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import api from '../api/client';
import TopBar from '../components/TopBar';
import Icon from '../components/ui/Icon';
import Avatar from '../components/ui/Avatar';
import Chip from '../components/ui/Chip';
import useLayout from '../components/ui/useLayout';

export default function OnboardingSuccessPage() {
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const { openMenu, openNotifications } = useLayout();
  const id = params.get('id');

  const [client, setClient] = useState(null);

  useEffect(() => {
    if (!id) return;
    api.get(`/clients/${id}`).then(setClient).catch(() => {});
  }, [id]);

  return (
    <>
      <TopBar
        crumbs={['Clients', 'Added']}
        onMenuClick={openMenu}
        onNotificationsClick={openNotifications}
      />
      <div className="page">
        <div className="page-head" style={{ justifyContent: 'center', textAlign: 'center' }}>
          <div style={{ maxWidth: 640 }}>
            <div className="eyebrow" style={{ marginBottom: 14 }}>Client created</div>
            <h1 className="page-title">
              <em>{client?.full_name || 'New client'}</em> is now<br />in your book.
            </h1>
            <p className="page-sub" style={{ margin: '16px auto 0' }}>
              Run a comparison, translate their plan documents, or verify their provider network — whatever kicks
              off the relationship.
            </p>
          </div>
        </div>

        {client && (
          <div className="card card-pad" style={{ maxWidth: 640, margin: '0 auto 24px' }}>
            <div className="row" style={{ gap: 16 }}>
              <Avatar name={client.full_name} size="lg" />
              <div style={{ flex: 1 }}>
                <div style={{ fontFamily: 'var(--serif)', fontSize: 22, letterSpacing: '-0.01em' }}>{client.full_name}</div>
                <div className="row" style={{ gap: 8, marginTop: 8, flexWrap: 'wrap' }}>
                  <Chip>Age {client.age}</Chip>
                  <Chip>ZIP {client.zip_code}</Chip>
                  <Chip>{client.income_level} income</Chip>
                  {client.prescriptions?.length > 0 && <Chip>{client.prescriptions.length} Rx</Chip>}
                  {client.doctors?.length > 0 && <Chip>{client.doctors.length} providers</Chip>}
                </div>
              </div>
            </div>
          </div>
        )}

        <div className="grid-3" style={{ maxWidth: 960, margin: '0 auto' }}>
          {[
            { icon: 'compare', label: 'Compare plans', desc: 'Find the best-fit Medicare Advantage plan.', path: '/compare', accent: true },
            { icon: 'translate', label: 'Translate coverage', desc: 'Decode any Summary of Benefits in plain English.', path: '/translator' },
            { icon: 'network', label: 'Verify network', desc: 'Confirm doctors and pharmacies are in-network.', path: '/network' },
          ].map((t) => (
            <div key={t.path} className="card card-pad" style={{ cursor: 'pointer' }} onClick={() => navigate(t.path)}>
              <div className="row" style={{ gap: 10, marginBottom: 12 }}>
                <Icon name={t.icon} size={18} className="ink-4" />
                <span className="eyebrow">Next step</span>
              </div>
              <div style={{ fontFamily: 'var(--serif)', fontSize: 22, letterSpacing: '-0.01em', marginBottom: 8 }}>
                {t.label}
              </div>
              <div className="muted" style={{ fontSize: 13, marginBottom: 14 }}>{t.desc}</div>
              <button className={`btn ${t.accent ? 'accent' : ''}`} style={{ width: '100%' }}>
                Open <Icon name="arrow_r" size={14} />
              </button>
            </div>
          ))}
        </div>

        <div className="row" style={{ justifyContent: 'center', marginTop: 32, gap: 12 }}>
          <button className="btn" onClick={() => navigate('/clients')}>
            <Icon name="users" size={14} /> All clients
          </button>
          <button className="btn primary" onClick={() => navigate(`/clients/${id}`)} disabled={!id}>
            View {client?.full_name?.split(' ')[0] || 'client'} <Icon name="arrow_r" size={14} />
          </button>
        </div>
      </div>
    </>
  );
}
