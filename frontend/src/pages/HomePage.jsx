import { useState, useRef, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { motion, AnimatePresence, useReducedMotion } from 'framer-motion';
import BrandLogo from '../components/ui/BrandLogo';
import '../home.css';

// Motion presets — reused across sections so the entrance language stays
// consistent. Honors prefers-reduced-motion via useReducedMotion below.
const fadeUp = {
  hidden: { opacity: 0, y: 18 },
  show: { opacity: 1, y: 0, transition: { duration: 0.55, ease: [0.22, 0.61, 0.36, 1] } },
};
const stagger = {
  hidden: {},
  show: { transition: { staggerChildren: 0.08, delayChildren: 0.05 } },
};
const inView = { initial: 'hidden', whileInView: 'show', viewport: { once: true, amount: 0.18 } };

const ARROW = (
  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
    <path d="M5 12h14M13 5l7 7-7 7" />
  </svg>
);
const ARROW_LG = (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
    <path d="M5 12h14M13 5l7 7-7 7" />
  </svg>
);

const AGENTS = [
  {
    key: 'compare', n: '01',
    icon: 'M21 3 3 21M9 3h12v12M15 21H3V9',
    title: 'Plan comparison',
    tab: 'Ranks plans against a client’s real meds & providers',
    desc: 'Weighs every available Medicare Advantage plan against the client’s prescriptions, doctors, and budget — then ranks by true annual cost, not sticker premium.',
    inLbl: 'Input', in: [['zip', '10025'], ['age', '67'], ['rx', '3 meds']],
    outLbl: 'Output', out: [['best', 'Aetna Prime'], ['est/yr', '$1,864'], ['fit', '96%']],
    chips: ['CMS 2026 filings', 'formulary-pinned', 'typed output'],
  },
  {
    key: 'translate', n: '02',
    icon: 'M5 8h14M7 5l5 6-5 6M13 13l4 8 4-8M15 17h8',
    title: 'Coverage translator',
    tab: 'Turns Summary-of-Benefits into plain English',
    desc: 'Answers benefit questions in plain language and cites the exact section it came from — so a broker never paraphrases a plan wrong.',
    inLbl: 'Asked', in: [['q', 'ER copay if admitted?']],
    outLbl: 'Answered', out: [['$120', 'waived if admitted'], ['cite', '§1.2 Emergency']],
    chips: ['section citations', 'no hallucinated benefits'],
  },
  {
    key: 'plan', n: '03',
    icon: 'M3 12a9 9 0 1 0 3-6.7L3 8M3 3v5h5M12 7v5l3 2',
    title: 'Temporal plan',
    tab: 'Turns a deadline into an ordered action list',
    desc: 'Takes an event — a denial, a life change, an enrollment window — and produces a dated, ordered action plan anchored to the real deadline.',
    inLbl: 'Event', in: [['type', 'SEP'], ['trigger', 'May 1']],
    outLbl: 'Plan', out: [['deadline', 'Jun 30'], ['actions', '5 steps'], ['urgency', 'high']],
    chips: ['date-anchored', 'owner-assigned'],
  },
  {
    key: 'verify', n: '04',
    icon: 'M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10zM9 12l2 2 4-4',
    title: 'Network verify',
    tab: 'Confirms doctors & pharmacies are in-network',
    desc: 'Checks a client’s providers, hospitals, and pharmacies against a plan’s live network before enrollment — and re-checks when carriers publish changes.',
    inLbl: 'Checking', in: [['Dr. Patel', 'cardiology'], ['pharmacy', 'mail-order']],
    outLbl: 'Result', out: [['Dr. Patel', 'in-network ✓'], ['pharmacy', 'in-network ✓']],
    chips: ['re-checks on change', 'provider-level'],
  },
  {
    key: 'appeal', n: '05',
    icon: 'M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8zM14 2v6h6M9 13h6M9 17h3',
    title: 'Appeal drafter',
    tab: 'Drafts denial appeals with cited guidance',
    desc: 'Drafts a denial appeal from the denial letter and the plan’s own language, citing the relevant CMS guidance — ready for a broker to review and file.',
    inLbl: 'Denial', in: [['claim', 'cardiac cath'], ['carrier', 'Cigna']],
    outLbl: 'Draft', out: [['cites', 'LCD L33559'], ['status', 'ready to file']],
    chips: ['CMS-cited', 'human-reviewed'],
  },
];

// Wrapper that fades + slides up the first time it enters the viewport.
// Replaces the previous IntersectionObserver-based Reveal so we can compose
// with stagger containers and benefit from framer-motion's reduced-motion
// handling.
function Reveal({ children, as = 'div', className = '', ...rest }) {
  const Tag = motion[as] || motion.div;
  return (
    <Tag variants={fadeUp} {...inView} className={className} {...rest}>
      {children}
    </Tag>
  );
}

// Variant of Reveal that staggers its direct children — used for the
// stat strip, 3-card regulated section, 4-step "how it works", etc.
function RevealGroup({ children, as = 'div', className = '', ...rest }) {
  const Tag = motion[as] || motion.div;
  return (
    <Tag variants={stagger} {...inView} className={className} {...rest}>
      {children}
    </Tag>
  );
}

function smoothScroll(e, id) {
  const t = document.getElementById(id);
  if (t) {
    e.preventDefault();
    t.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }
}

// Demo-video frame. The <video> uses preload="none", so nothing is fetched
// until a visitor clicks play — the placeholder (with drop-in instructions)
// stays until a real file loads, then hides. The file lives at
// frontend/public/product-demo.mp4 and is served at /product-demo.mp4.
// NOTE: the name must NOT start with "health" — vite.config.js proxies the
// /health prefix to the backend, so /healthflow-*.mp4 would 404 in dev.
function DemoVideoFrame() {
  const videoRef = useRef(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    const v = videoRef.current;
    if (!v) return;
    const show = () => setReady(true);
    const hide = () => setReady(false);
    v.addEventListener('loadeddata', show); // fires only when a decodable file is attached
    v.addEventListener('error', hide, true); // a missing/invalid source bubbles up
    if (v.readyState >= 2) show(); // already cached
    return () => {
      v.removeEventListener('loadeddata', show);
      v.removeEventListener('error', hide, true);
    };
  }, []);

  const play = () => { videoRef.current?.play().catch(() => {}); };

  return (
    <Reveal as="figure" className="video-frame">
      <div className="vf-chrome">
        <span className="vf-dot"></span><span className="vf-dot"></span><span className="vf-dot"></span>
        <span className="vf-url">app.healthflow.work — product demo</span>
      </div>
      <div className="vf-stage">
        {/* Demo file lives at frontend/public/product-demo.mp4 (served at /product-demo.mp4). */}
        <video ref={videoRef} className="vf-video" controls preload="none" playsInline>
          <source src="/product-demo.mp4" type="video/mp4" />
          Your browser doesn't support embedded video.
        </video>
        <button
          className={`vf-placeholder${ready ? ' hide' : ''}`}
          type="button"
          onClick={play}
          aria-label="Play demo video"
        >
          <span className="vf-play">
            <svg width="26" height="26" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M8 5v14l11-7z" /></svg>
          </span>
          <span className="vf-ph-title">Watch the product demo</span>
          <span className="vf-ph-desc">
            Click to play. To swap the clip, replace <code>frontend/public/product-demo.mp4</code> —
            it appears here automatically. MP4 (H.264) plays everywhere; keep it under ~50&nbsp;MB for fast loading.
          </span>
        </button>
      </div>
    </Reveal>
  );
}

export default function HomePage() {
  const [active, setActive] = useState('compare');
  const agent = AGENTS.find((a) => a.key === active);
  const reduceMotion = useReducedMotion();

  return (
    <div className="lp">
      {/* NAV */}
      <nav className="lp-nav">
        <div className="lp-nav-inner">
          <a className="lp-logo" href="#top" onClick={(e) => smoothScroll(e, 'top')}>
            <BrandLogo size={30} />
            <span className="wm">HealthFlow</span>
          </a>
          <div className="lp-navlinks">
            <a href="#system" onClick={(e) => smoothScroll(e, 'system')}>System</a>
            <a href="#agents" onClick={(e) => smoothScroll(e, 'agents')}>Agents</a>
            <a href="#regulated" onClick={(e) => smoothScroll(e, 'regulated')}>Compliance</a>
            <a href="#demo" onClick={(e) => smoothScroll(e, 'demo')}>Demo</a>
            <a href="#how" onClick={(e) => smoothScroll(e, 'how')}>How it works</a>
          </div>
          <div className="lp-nav-cta">
            <Link className="lp-btn secondary" to="/login">Sign in</Link>
            <Link className="lp-btn" to="/login?mode=register">Request access {ARROW}</Link>
          </div>
        </div>
      </nav>

      {/* HERO */}
      <header className="lp-section lp-hero" id="top">
        <div className="lp-wrap">
          <div className="lp-hero-grid">
            <motion.div initial="hidden" animate="show" variants={stagger}>
              <motion.span className="lp-eyebrow" variants={fadeUp}>
                <span className="pulse"></span> Multi-agent · regulated by Saidu Kamara
              </motion.span>
              <motion.h1 className="lp-h1" variants={fadeUp}>
                Coverage advice you can <em>defend</em> — months later, under audit.
              </motion.h1>
              <motion.p className="lp-hero-sub" variants={fadeUp}>
                HealthFlow is the agent workspace Medicare brokers use to compare plans, translate dense
                benefits, and draft appeals — with an attributable, PHI-aware record under every recommendation.
              </motion.p>
              <motion.div className="lp-hero-actions" variants={fadeUp}>
                <Link className="lp-btn lg" to="/login?mode=register">Request access {ARROW_LG}</Link>
                <a className="lp-btn ghost lg" href="#system" onClick={(e) => smoothScroll(e, 'system')}>See the system</a>
              </motion.div>
              <motion.div className="lp-hero-stats" variants={stagger}>
                <motion.div className="s" variants={fadeUp}><div className="n">5 agents</div><div className="l">one orchestrated workflow</div></motion.div>
                <motion.div className="s" variants={fadeUp}><div className="n">100%</div><div className="l">actions logged &amp; attributable</div></motion.div>
                <motion.div className="s" variants={fadeUp}><div className="n">SOC 2 · HIPAA</div><div className="l">tenant-isolated by default</div></motion.div>
              </motion.div>
            </motion.div>

            {/* agent-flow motif */}
            <Reveal className="flowcard" id="system">
              <div className="fc-head">
                <span className="fc-title">Request lifecycle</span>
                <span className="fc-live"><span className="d"></span> Live</span>
              </div>
              <svg viewBox="0 0 460 360" role="img" aria-label="Agent flow: a client request is routed by an orchestrator to specialized agents and recorded in an immutable audit log.">
                <path className="flow-path" d="M120 64 C 180 64, 180 120, 230 120" />
                <path className="flow-dash" d="M120 64 C 180 64, 180 120, 230 120" />
                <path className="flow-path" d="M340 120 C 380 120, 380 175, 410 175" />
                <path className="flow-path" d="M230 140 C 150 150, 120 175, 120 185" />
                <path className="flow-path" d="M230 140 C 200 175, 210 175, 215 185" />
                <path className="flow-path" d="M286 140 C 300 175, 305 175, 312 185" />
                <path className="flow-dash" d="M230 140 C 150 150, 120 175, 120 185" />
                <path className="flow-dash" d="M286 140 C 300 175, 305 175, 312 185" />
                <path className="flow-path" d="M120 235 C 120 270, 200 280, 230 290" />
                <path className="flow-path" d="M215 235 C 230 270, 230 280, 230 290" />
                <path className="flow-path" d="M312 235 C 312 270, 260 280, 230 290" />
                <path className="flow-dash" d="M215 235 C 230 270, 230 280, 230 290" />

                <g>
                  <rect className="flow-rect" x="20" y="44" width="100" height="40" rx="8" />
                  <text className="flow-node-label" x="38" y="62">REQUEST</text>
                  <text className="flow-node-sub" x="38" y="75">client intake</text>
                </g>
                <g>
                  <rect className="flow-rect accent" x="230" y="100" width="110" height="44" rx="8" />
                  <text className="flow-node-label" x="246" y="120">ORCHESTRATOR</text>
                  <text className="flow-node-sub" x="246" y="133">routes &amp; verifies</text>
                </g>
                <g>
                  <rect className="flow-rect" x="70" y="185" width="100" height="50" rx="8" />
                  <text className="flow-node-label" x="84" y="206">COMPARE</text>
                  <text className="flow-node-sub" x="84" y="219">plan ranking</text>
                </g>
                <g>
                  <rect className="flow-rect" x="178" y="185" width="74" height="50" rx="8" />
                  <text className="flow-node-label" x="190" y="206">TRANSLATE</text>
                  <text className="flow-node-sub" x="190" y="219">benefits</text>
                </g>
                <g>
                  <rect className="flow-rect" x="262" y="185" width="100" height="50" rx="8" />
                  <text className="flow-node-label" x="276" y="206">PLAN</text>
                  <text className="flow-node-sub" x="276" y="219">deadlines</text>
                </g>
                <g>
                  <rect className="flow-rect" x="380" y="155" width="70" height="40" rx="8" />
                  <text className="flow-node-label" x="392" y="173">VERIFY</text>
                  <text className="flow-node-sub" x="392" y="186">network</text>
                </g>
                <g>
                  <rect className="flow-rect" x="120" y="290" width="220" height="46" rx="8" />
                  <text className="flow-node-label" x="138" y="311">AUDIT LOG</text>
                  <text className="flow-node-sub" x="138" y="324">immutable · hashed · attributable</text>
                  <circle className="flow-dot-pulse" cx="322" cy="313" r="3" />
                </g>
              </svg>
            </Reveal>
          </div>
        </div>
      </header>

      {/* TRUST STRIP */}
      <div className="lp-trust">
        <div className="lp-trust-inner">
          <span className="lbl">Reads from</span>
          <div className="marks">
            <span className="mark">Aetna</span>
            <span className="mark">Humana</span>
            <span className="mark">UnitedHealthcare</span>
            <span className="mark">CMS Plan Finder</span>
          </div>
          <div className="marks" style={{ marginLeft: 'auto' }}>
            <span className="badge">SOC 2 Type II</span>
            <span className="badge">HIPAA</span>
          </div>
        </div>
      </div>

      {/* PROBLEM */}
      <section className="lp-section lp-problem">
        <div className="lp-wrap">
          <Reveal className="sec-marker">
            <span className="idx">01</span> <span className="ln"></span> The problem
          </Reveal>
          <div className="lp-problem-grid">
            <Reveal as="blockquote" className="quote">
              A broker advises a 67-year-old on the plan that won't bankrupt her if she gets sick. Then has to <em>defend that call</em> a year later.
            </Reveal>
            <Reveal className="body">
              <p>Medicare Advantage is a maze of formularies, networks, and deadlines that shift every plan year. The advice a broker gives is high-stakes — and increasingly, it's regulated.</p>
              <p>Most tools in this space are spreadsheets with a chat box bolted on. They produce an answer, then forget how they got there. When a denial gets appealed or a regulator asks <strong>"why this plan?"</strong> — there's nothing to point to.</p>
              <p>HealthFlow treats every recommendation as a <strong>compliance event</strong>: routed through specialized agents, grounded in live carrier data, and recorded so it holds up when it matters.</p>
            </Reveal>
          </div>
        </div>
      </section>

      {/* AGENT SYSTEM */}
      <section className="lp-section" id="agents">
        <div className="lp-wrap">
          <Reveal className="sec-marker">
            <span className="idx">02</span> <span className="ln"></span> The agent system
          </Reveal>
          <Reveal as="h2" className="sec-title">Five specialized agents. One orchestrated workflow.</Reveal>
          <Reveal as="p" className="sec-lead">
            Each agent does one job well and hands off through the orchestrator — not a single model guessing at everything. Every input and output is typed, grounded, and logged.
          </Reveal>

          <Reveal className="agents-grid">
            <div className="agent-tabs">
              {AGENTS.map((a) => (
                <button
                  key={a.key}
                  className={`agent-tab ${a.key === active ? 'on' : ''}`}
                  onClick={() => setActive(a.key)}
                  type="button"
                >
                  <span className="ti">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                      <path d={a.icon} />
                    </svg>
                  </span>
                  <span>
                    <span className="tt">{a.title}</span>
                    <span className="td">{a.tab}</span>
                  </span>
                  <span className="num">{a.n}</span>
                </button>
              ))}
            </div>
            <div className="agent-panel" style={{ overflow: 'hidden' }}>
              <AnimatePresence mode="wait" initial={false}>
                <motion.div
                  key={agent.key}
                  initial={reduceMotion ? false : { opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={reduceMotion ? { opacity: 0 } : { opacity: 0, y: -8 }}
                  transition={{ duration: 0.28, ease: [0.22, 0.61, 0.36, 1] }}
                >
                  <div className="ap-eyebrow">Agent {agent.n}</div>
                  <div className="ap-title">{agent.title}</div>
                  <div className="ap-desc">{agent.desc}</div>
                  <div className="ap-io">
                    <div className="io-box">
                      <div className="io-lbl">{agent.inLbl}</div>
                      {agent.in.map(([k, v], i) => (
                        <div key={i} className="io-line"><span className="k">{k}</span> {v}</div>
                      ))}
                    </div>
                    <div className="arrow">
                      <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
                        <path d="M5 12h14M13 5l7 7-7 7" />
                      </svg>
                    </div>
                    <div className="io-box">
                      <div className="io-lbl">{agent.outLbl}</div>
                      {agent.out.map(([k, v], i) => (
                        <div key={i} className="io-line"><span className="k">{k}</span> {v}</div>
                      ))}
                    </div>
                  </div>
                  <div className="ap-foot">
                    {agent.chips.map((c) => <span key={c} className="ap-chip">{c}</span>)}
                  </div>
                </motion.div>
              </AnimatePresence>
            </div>
          </Reveal>
        </div>
      </section>

      {/* REGULATED (dark) */}
      <section className="lp-section lp-reg" id="regulated">
        <div className="lp-wrap">
          <Reveal className="sec-marker">
            <span className="idx">03</span> <span className="ln"></span> Built for regulated environments
          </Reveal>
          <Reveal as="h2" className="sec-title">The part most AI tools skip.</Reveal>
          <Reveal as="p" className="sec-lead">
            PHI doesn't tolerate "move fast and break things." The architecture is the product: forensic logging, data minimization, and hard tenant boundaries — not features bolted on after a breach.
          </Reveal>

          <RevealGroup className="reg-grid">
            <motion.div className="reg-card" variants={fadeUp}>
              <div className="rc-ic">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M3 12a9 9 0 1 0 3-6.7L3 8" />
                  <path d="M3 3v5h5M12 7v5l3 2" />
                </svg>
              </div>
              <div className="rc-title">Audit-grade forensics</div>
              <div className="rc-desc">Every agent action is appended to an immutable, hash-chained log — who, what, which data version, and why. Reconstruct any recommendation, exactly, on demand.</div>
              <div className="rc-demo">
                <div className="audit-row"><span className="ts">09:42:07</span><span className="ev">compare.run <span className="hash">#a3f… signed</span></span></div>
                <div className="audit-row"><span className="ts">09:42:07</span><span className="ev">formulary@2026.4 pinned</span></div>
                <div className="audit-row"><span className="ts">09:42:09</span><span className="ev">rec emitted <span className="hash">#b1c… by SK</span></span></div>
              </div>
            </motion.div>

            <motion.div className="reg-card" variants={fadeUp}>
              <div className="rc-ic">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
                  <path d="M9 12l2 2 4-4" />
                </svg>
              </div>
              <div className="rc-title">PHI-conscious by default</div>
              <div className="rc-desc">Identifiers are minimized and masked before they reach a model. Agents reason over the clinical shape of a case — not the patient's name, ID, or address.</div>
              <div className="rc-demo">
                <div className="phi-line"><span className="k">member</span><span className="phi-mask">▮▮▮▮▮▮▮▮</span></div>
                <div className="phi-line"><span className="k">medicare_id</span><span className="phi-mask">1EG4-▮▮▮-▮▮72</span></div>
                <div className="phi-line"><span className="k">conditions</span><span className="ok">visible to agent ✓</span></div>
              </div>
            </motion.div>

            <motion.div className="reg-card" variants={fadeUp}>
              <div className="rc-ic">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                  <rect x="3" y="11" width="18" height="11" rx="2" />
                  <path d="M7 11V7a5 5 0 0 1 10 0v4" />
                </svg>
              </div>
              <div className="rc-title">Hard tenant isolation</div>
              <div className="rc-desc">Every agency's data lives behind its own boundary — separate keys, separate stores, no shared context window. One broker's book can never leak into another's.</div>
              <div className="rc-demo">
                <div className="tenant-row"><span className="box">tenant: kamara-benefits</span><span className="lock">🔒</span></div>
                <div className="tenant-row"><span className="box">tenant: atlas-advisors</span><span className="lock">🔒</span></div>
                <div className="tenant-row"><span className="box" style={{ opacity: 0.5 }}>cross-tenant read</span><span style={{ color: 'oklch(0.6 0.12 25)' }}>denied</span></div>
              </div>
            </motion.div>
          </RevealGroup>
        </div>
      </section>

      {/* HOW IT WORKS */}
      <section className="lp-section" id="how">
        <div className="lp-wrap">
          <Reveal className="sec-marker">
            <span className="idx">04</span> <span className="ln"></span> How it works
          </Reveal>
          <Reveal as="h2" className="sec-title">From a client's situation to a recommendation that holds up.</Reveal>
          <RevealGroup className="steps">
            <motion.div className="step" variants={fadeUp}><div className="sn">01</div><div className="st">Intake</div><div className="sd">A client's meds, providers, and budget enter once. PHI is minimized at the door.</div></motion.div>
            <motion.div className="step" variants={fadeUp}><div className="sn">02</div><div className="st">Orchestrate</div><div className="sd">The orchestrator routes the case to the agents it needs and pins the live data versions.</div></motion.div>
            <motion.div className="step" variants={fadeUp}><div className="sn">03</div><div className="st">Reason</div><div className="sd">Agents compare plans, translate benefits, and surface deadlines — each output grounded and typed.</div></motion.div>
            <motion.div className="step" variants={fadeUp}><div className="sn">04</div><div className="st">Record</div><div className="sd">The recommendation and its full lineage are signed into the audit log. Defensible later, by design.</div></motion.div>
          </RevealGroup>
        </div>
      </section>

      {/* DEMO VIDEO */}
      <section className="lp-section lp-demo" id="demo">
        <div className="lp-wrap">
          <Reveal className="sec-marker">
            <span className="idx">05</span> <span className="ln"></span> See it in action
          </Reveal>
          <Reveal as="h2" className="sec-title">Watch a recommendation come together.</Reveal>
          <Reveal as="p" className="sec-lead">
            A short walkthrough — from a client's intake to a ranked plan, a plain-English benefit answer,
            and a signed entry in the audit log.
          </Reveal>
          <DemoVideoFrame />
        </div>
      </section>

      {/* CTA */}
      <section className="lp-cta">
        <div className="lp-wrap">
          <Reveal as="div" className="k">For independent Medicare brokers &amp; agencies</Reveal>
          <Reveal as="h2">Give every recommendation a <em>paper trail.</em></Reveal>
          <Reveal as="p" className="sub">Set up your workspace in an afternoon. Bring your book; keep your license clean.</Reveal>
          <Reveal className="actions">
            <Link className="lp-btn lg" to="/login?mode=register">Request access {ARROW_LG}</Link>
            <Link className="lp-btn ghost lg" to="/login">Explore the workspace</Link>
          </Reveal>
        </div>
      </section>

      {/* FOOTER */}
      <footer className="lp-footer">
        <div className="lp-wrap">
          <div className="lp-footer-grid">
            <div className="fcol fbrand">
              <div className="lp-logo">
                <BrandLogo size={28} />
                <span className="wm">HealthFlow</span>
              </div>
              <p>Multi-agent infrastructure for health coverage decisions that have to hold up later.</p>
            </div>
            <div className="fcol">
              <h4>Product</h4>
              <a href="#agents" onClick={(e) => smoothScroll(e, 'agents')}>Agents</a>
              <a href="#regulated" onClick={(e) => smoothScroll(e, 'regulated')}>Compliance</a>
              <a href="#how" onClick={(e) => smoothScroll(e, 'how')}>How it works</a>
              <Link to="/login">Workspace</Link>
            </div>
            <div className="fcol">
              <h4>Company</h4>
              <a href="https://github.com/saikamara59/health-insurance-agent" target="_blank" rel="noreferrer">About</a>
              <a href="#regulated" onClick={(e) => smoothScroll(e, 'regulated')}>Security</a>
              <a href="mailto:mhsaidu@gmail.com">Contact</a>
            </div>
            <div className="fcol">
              <h4>Legal</h4>
              <a href="#regulated" onClick={(e) => smoothScroll(e, 'regulated')}>HIPAA notice</a>
              <a href="https://healthflow.work" target="_blank" rel="noreferrer">Status</a>
            </div>
          </div>
          <div className="lp-footer-base">
            <span>© 2026 HealthFlow — built by Saidu Kamara. Not affiliated with CMS or Medicare.</span>
            <div className="legal">
              <a href="https://github.com/saikamara59/health-insurance-agent" target="_blank" rel="noreferrer">GitHub</a>
            </div>
          </div>
        </div>
      </footer>
    </div>
  );
}
