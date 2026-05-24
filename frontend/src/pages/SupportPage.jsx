import TopBar from '../components/TopBar';
import Icon from '../components/ui/Icon';
import useLayout from '../components/ui/useLayout';

const RESOURCES = [
  {
    title: 'Plan comparison',
    desc: 'How the cost ranking works, what CMS data feeds it, and how to override the recommendation.',
    icon: 'compare',
  },
  {
    title: 'Temporal plan',
    desc: 'Map a client\'s next 12 months — enrollment windows, renewal dates, and the SEPs they\'re eligible for.',
    icon: 'history',
  },
  {
    title: 'Coverage translator',
    desc: 'What kinds of documents work best. Citations, formulary tiers, and section-level quoting.',
    icon: 'translate',
  },
  {
    title: 'Network verification',
    desc: 'How the NPI registry and formulary lookups work. Warning codes and what to do about them.',
    icon: 'network',
  },
  {
    title: 'Cost calculator',
    desc: 'The math behind annual projections — premiums, deductible burn, copays, and OOP caps.',
    icon: 'calculator',
  },
  {
    title: 'Claim appeals',
    desc: 'Denial-code parsing, CMS appeal grounds, and template customization.',
    icon: 'appeal',
  },
  {
    title: 'Feedback & RLHF',
    desc: 'How your ratings feed the weekly reward model and improve agent outputs.',
    icon: 'feedback',
  },
];

export default function SupportPage() {
  const { openMenu, openNotifications } = useLayout();
  return (
    <>
      <TopBar crumbs={['Review', 'Support']} onMenuClick={openMenu} onNotificationsClick={openNotifications} />
      <div className="page">
        <div className="page-head">
          <div>
            <div className="eyebrow" style={{ marginBottom: 14 }}>How it works</div>
            <h1 className="page-title"><em>Support</em></h1>
            <p className="page-sub">
              Short explainers for each tool, plus a direct line if something's unclear. HealthFlow is new — if you
              hit a rough edge, tell us.
            </p>
          </div>
        </div>

        <div className="grid-3">
          {RESOURCES.map((r) => (
            <div key={r.title} className="card card-pad">
              <div className="row" style={{ gap: 10, marginBottom: 10 }}>
                <Icon name={r.icon} size={18} className="ink-4" />
                <span className="eyebrow">Topic</span>
              </div>
              <div style={{ fontFamily: 'var(--serif)', fontSize: 20, letterSpacing: '-0.01em', marginBottom: 8 }}>
                {r.title}
              </div>
              <div className="muted" style={{ fontSize: 13.5, lineHeight: 1.6 }}>{r.desc}</div>
            </div>
          ))}
        </div>

        <div className="section-head"><h2>Still stuck?</h2></div>
        <div className="card card-pad" style={{ maxWidth: 720 }}>
          <p style={{ fontSize: 14, color: 'var(--ink-2)', lineHeight: 1.7, marginBottom: 20 }}>
            HealthFlow is built and maintained by Saidu Kamara. For feature requests, bug reports, or a walkthrough of
            the tools, email directly — typical response within one business day.
          </p>
          <a href="mailto:mhsaidu@gmail.com" className="btn accent">
            <Icon name="send" size={14} /> Email support
          </a>
        </div>
      </div>
    </>
  );
}
