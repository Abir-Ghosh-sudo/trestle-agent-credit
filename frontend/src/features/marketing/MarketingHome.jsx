/**
 * MarketingHome.jsx — Trestle marketing homepage (Obsidian dark theme).
 *
 * Structure: hero → ticker → stats → features → how-it-works →
 * credit tiers ("pricing") → testimonials → FAQ → network proof → CTA.
 *
 * Testimonials are clearly-generic placeholder personas (not real named
 * individuals) — swap in real user quotes once you have them.
 */

import React, { useState } from "react";
import { motion } from "framer-motion";
import {
  Diamond, TrendingUp, Layers, RefreshCw, Zap, ShieldAlert,
  ArrowRight, ExternalLink, ChevronDown, Quote, Sparkles, Radio,
} from "lucide-react";
import { APP_ID } from "../../lib/contract.js";

const fadeUp = {
  hidden: { opacity: 0, y: 28 },
  show: { opacity: 1, y: 0, transition: { duration: 0.6, ease: [0.22, 1, 0.36, 1] } },
};
const stagger = {
  hidden: {},
  show: { transition: { staggerChildren: 0.08 } },
};

function Reveal({ children, className, as: Tag = motion.div, ...props }) {
  return (
    <Tag
      variants={fadeUp}
      initial="hidden"
      whileInView="show"
      viewport={{ once: true, margin: "-80px" }}
      className={className}
      {...props}
    >
      {children}
    </Tag>
  );
}

function TickerStrip({ text }) {
  const repeated = Array.from({ length: 6 }, (_, i) => i);
  return (
    <div className="w-full overflow-hidden bg-brand-gradient py-3">
      <div className="inline-flex whitespace-nowrap animate-marquee font-pixel text-sm font-bold tracking-[0.2em] uppercase text-white">
        {repeated.map((i) => (
          <span key={i} className="mx-6 flex items-center gap-6">
            {text}
            <span className="opacity-60">◆</span>
          </span>
        ))}
      </div>
    </div>
  );
}

function FloatingBlob({ className, gradient, delay = 0 }) {
  return (
    <div
      className={`floating-blob ${className}`}
      style={{ background: gradient, animationDelay: `${delay}s` }}
    />
  );
}

function Counter({ value, suffix = "" }) {
  return (
    <span className="font-display font-bold text-4xl gradient-text">
      {value}
      <span className="text-lg text-text-muted ml-1 font-pixel align-middle">{suffix}</span>
    </span>
  );
}

function StatTile({ label, value, suffix }) {
  return (
    <Reveal className="glass-panel p-6 flex flex-col items-center justify-center text-center">
      <Counter value={value} suffix={suffix} />
      <div className="font-sans text-sm font-medium text-text-secondary mt-2">{label}</div>
    </Reveal>
  );
}

function FeatureCard({ icon: Icon, title, description }) {
  return (
    <Reveal className="float-card p-7 flex flex-col items-start group">
      <div className="w-14 h-14 rounded-2xl bg-brand-gradient shadow-glow-accent flex items-center justify-center mb-6 transition-transform duration-300 group-hover:scale-110 group-hover:rotate-3">
        <Icon size={24} className="text-white" strokeWidth={2} />
      </div>
      <h3 className="font-display font-semibold text-lg text-text-primary mb-3">{title}</h3>
      <p className="font-body text-[15px] text-text-secondary leading-relaxed">{description}</p>
    </Reveal>
  );
}

function TimelineStep({ number, title, description, isLast }) {
  return (
    <Reveal className="flex gap-5">
      <div className="flex flex-col items-center">
        <div className="w-11 h-11 flex items-center justify-center shrink-0 font-pixel text-base font-bold rounded-2xl bg-brand-gradient text-white shadow-soft-md">
          {number}
        </div>
        {!isLast && <div className="w-0.5 flex-1 my-2 bg-gradient-to-b from-accent/40 to-transparent rounded-full" />}
      </div>
      <div className="pb-10 pt-1">
        <h4 className="font-display font-semibold text-base text-text-primary mb-2">{title}</h4>
        <p className="font-body text-[15px] text-text-secondary leading-relaxed glass-panel px-4 py-3 !shadow-soft-sm">
          {description}
        </p>
      </div>
    </Reveal>
  );
}

function TestimonialCard({ quote, name, role }) {
  return (
    <Reveal className="float-card p-6 flex flex-col">
      <Quote size={22} className="text-accent mb-4" strokeWidth={2} />
      <p className="font-body text-[15px] text-text-secondary leading-relaxed mb-6 flex-1">
        "{quote}"
      </p>
      <div className="flex items-center gap-3">
        <div className="w-9 h-9 rounded-full bg-brand-gradient flex items-center justify-center font-display font-bold text-xs text-white">
          {name.charAt(0)}
        </div>
        <div>
          <div className="font-display font-semibold text-sm text-text-primary">{name}</div>
          <div className="font-body text-xs text-text-muted">{role}</div>
        </div>
      </div>
    </Reveal>
  );
}

function FaqItem({ q, a, isOpen, onToggle }) {
  return (
    <Reveal className="glass-panel overflow-hidden">
      <button
        onClick={onToggle}
        className="w-full flex items-center justify-between gap-4 p-5 text-left"
        aria-expanded={isOpen}
      >
        <span className="font-display font-semibold text-[15px] text-text-primary">{q}</span>
        <ChevronDown
          size={18}
          className={`shrink-0 text-text-muted transition-transform duration-300 ${isOpen ? "rotate-180 text-accent" : ""}`}
        />
      </button>
      <motion.div
        initial={false}
        animate={{ height: isOpen ? "auto" : 0, opacity: isOpen ? 1 : 0 }}
        transition={{ duration: 0.25, ease: [0.22, 1, 0.36, 1] }}
        className="overflow-hidden"
      >
        <p className="font-body text-sm text-text-secondary leading-relaxed px-5 pb-5">{a}</p>
      </motion.div>
    </Reveal>
  );
}

const FEATURES = [
  { icon: Diamond, title: "Stake & Lock", description: "Your stake is your trust signal — lock ALGO to unlock your agent's credit limit." },
  { icon: TrendingUp, title: "Build History", description: "Record payments on-chain. Each positive interaction boosts your algorithmic score." },
  { icon: Layers, title: "Draw Credit", description: "Borrow ALGO after the LLM oracle approves your task. Caps rise from 0.1→5 ALGO as you level up." },
  { icon: RefreshCw, title: "Repay & Grow", description: "Settle debt to dynamically increase credit limits. Prove reliability, gain capital." },
  { icon: Zap, title: "Instant Auth", description: "Operations settle in seconds. Algorand's speed enables high-frequency agent actions." },
  { icon: ShieldAlert, title: "Trust Protocol", description: "Bad actors get slashed. Defaulters lose their stake instantly to the treasury." },
];

const STEPS = [
  { number: "01", title: "Agent Opt-in", description: "Connect a smart contract wallet. Stake a min of 1 ALGO to register identity." },
  { number: "02", title: "Do Work", description: "Perform actions online. Push proof of economic activity on-chain to boost credit." },
  { number: "03", title: "Take Loans", description: "Pull ALGO out of thin air backed entirely by your on-chain track record." },
  { number: "04", title: "Settle Up", description: "Repay before the 86,400-round (~24hr) deadline. Miss it and anyone can liquidate your stake." },
];

const TIERS = [
  { label: "Fresh", sub: "0 payments", formula: "0.1 ALGO / draw", featured: false },
  { label: "Trusted", sub: "10+ payments", formula: "0.5 ALGO / draw", featured: false },
  { label: "Veteran", sub: "50+ payments", formula: "2.0 ALGO / draw", featured: true },
  { label: "Elite", sub: "100+ payments", formula: "5.0 ALGO / draw", featured: false },
];

// Generic placeholder personas — not real people. Replace with real quotes
// once you have user testimonials.
const TESTIMONIALS = [
  { quote: "Our agent fleet went from needing manual top-ups to fully self-financing operations overnight.", name: "Autonomous trading desk", role: "Early integrator" },
  { quote: "The LLM gate caught a bad draw request in testing that would've drained our stake. That alone justified adopting it.", name: "Agent infra team", role: "Beta tester" },
  { quote: "Tier progression gives our agents a real incentive to behave well on-chain, not just once but continuously.", name: "DeFi automation studio", role: "Early integrator" },
];

const FAQS = [
  { q: "What is Trestle?", a: "Trestle is an on-chain credit protocol built for autonomous AI agents on Algorand. Agents stake ALGO, build an on-chain payment history, and draw algorithmically-sized credit — gated by an LLM oracle that evaluates each request before approval." },
  { q: "Do I need to be a developer to use this?", a: "You need a smart-contract-capable wallet (Pera or Defly) and basic comfort connecting agents to Algorand. The SDK handles the on-chain plumbing." },
  { q: "What happens if an agent defaults?", a: "Miss the ~24 hour repayment window and anyone can permissionlessly liquidate the stake — it's slashed to the treasury. This is what keeps the credit line trustless." },
  { q: "Is this live on mainnet?", a: "Currently deployed and tested on Algorand TestNet. Deploy your own instance via contracts/deploy.py to try it with your own account." },
];

export default function MarketingHome({ onLaunchApp }) {
  const [openFaq, setOpenFaq] = useState(0);

  return (
    <div className="relative min-h-screen pb-20 overflow-hidden">

      {/* ── HERO ── */}
      <section className="relative min-h-[88vh] flex flex-col items-center justify-center px-4 pt-24 pb-10">
        <FloatingBlob className="w-72 h-72 top-24 left-[8%] opacity-70" gradient="linear-gradient(135deg,#8b5cf6,#7c6df8)" />
        <FloatingBlob className="w-56 h-56 top-1/3 right-[10%] opacity-60" gradient="linear-gradient(135deg,#22d3ee,#7c6df8)" delay={1.5} />
        <FloatingBlob className="w-40 h-40 bottom-16 left-[20%] opacity-50" gradient="linear-gradient(135deg,#fbbf24,#fb7185)" delay={3} />
        <div className="hero-glow" />

        <motion.div
          initial="hidden"
          animate="show"
          variants={stagger}
          className="max-w-[880px] mx-auto text-center w-full relative z-10 flex flex-col items-center"
        >
          <motion.div variants={fadeUp} className="badge-chip badge-accent mb-8">
            <span className="font-pixel text-xs uppercase font-bold flex items-center gap-2">
              <Sparkles size={12} strokeWidth={2.5} /> For Autonomous Agents
            </span>
          </motion.div>

          <motion.h1
            variants={fadeUp}
            className="font-display font-bold text-[2.6rem] sm:text-6xl lg:text-7xl leading-[1.08] mb-8 max-w-[760px] mx-auto text-text-primary"
          >
            On-chain credit,
            <br />
            <span className="gradient-text">built for machines.</span>
          </motion.h1>

          <motion.p variants={fadeUp} className="font-body text-lg text-text-secondary max-w-xl mx-auto leading-relaxed mb-10">
            The first on-chain credit protocol for AI agents. Stake ALGO. Build reputation. Draw credit — with no human in the loop.
          </motion.p>

          <motion.div variants={fadeUp} className="flex flex-col sm:flex-row items-center justify-center gap-4">
            <motion.button
              whileHover={{ y: -3, scale: 1.02 }}
              whileTap={{ y: 0, scale: 0.98 }}
              transition={{ type: "spring", stiffness: 400, damping: 25 }}
              onClick={onLaunchApp}
              className="h-14 px-9 rounded-full bg-brand-gradient text-white shadow-soft-lg flex items-center gap-2 font-display font-semibold text-base"
            >
              Launch Protocol <ArrowRight size={17} strokeWidth={2.5} />
            </motion.button>
            <a
              href={`https://testnet.explorer.perawallet.app/application/${APP_ID}/`}
              target="_blank"
              rel="noopener noreferrer"
              className="h-14 px-9 rounded-full glass-panel !shadow-soft-sm flex items-center gap-2 font-display font-semibold text-base text-text-primary hover:!shadow-soft-md transition-all"
            >
              View Contract <ExternalLink size={15} strokeWidth={2.25} />
            </a>
          </motion.div>
        </motion.div>
      </section>

      <TickerStrip text="Trustless Algorithmic Credit" />

      {/* ── PROTOCOL STATS ── */}
      <section className="relative py-20 px-4">
        <div className="max-w-[960px] mx-auto">
          <Reveal as={motion.h2} className="font-display font-semibold text-2xl text-text-primary mb-10 text-center">
            The numbers behind the protocol
          </Reveal>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-5">
            <StatTile label="LLM Gate" value="4" suffix="criteria" />
            <StatTile label="Min Stake" value="1" suffix="ALGO" />
            <StatTile label="On-Chain" value="100" suffix="%" />
            <StatTile label="Repay Window" value="24" suffix="hrs" />
          </div>
        </div>
      </section>

      {/* ── FEATURES GRID ── */}
      <section className="relative py-20 px-4">
        <div className="max-w-[1040px] mx-auto">
          <Reveal className="mb-14 flex flex-col items-center text-center">
            <h2 className="font-display font-bold text-3xl md:text-4xl text-text-primary">
              Everything an agent needs to borrow
            </h2>
            <p className="font-body text-lg text-text-secondary mt-4 max-w-md">
              Features designed for agents moving at machine speed.
            </p>
          </Reveal>

          <motion.div
            variants={stagger}
            initial="hidden"
            whileInView="show"
            viewport={{ once: true, margin: "-60px" }}
            className="grid grid-cols-1 md:grid-cols-3 gap-6"
          >
            {FEATURES.map((f) => <FeatureCard key={f.title} {...f} />)}
          </motion.div>
        </div>
      </section>

      <TickerStrip text="Stake Your ALGO" />

      {/* ── HOW IT WORKS + TIER PRICING ── */}
      <section className="relative py-20 px-4">
        <div className="max-w-[1040px] mx-auto grid grid-cols-1 lg:grid-cols-2 gap-16">
          <div>
            <Reveal as={motion.h2} className="font-display font-bold text-2xl md:text-3xl text-text-primary mb-10">
              How it works
            </Reveal>
            {STEPS.map((s, i) => (
              <TimelineStep key={s.number} {...s} isLast={i === STEPS.length - 1} />
            ))}
          </div>

          <div>
            <Reveal as={motion.h2} className="font-display font-bold text-2xl md:text-3xl text-text-primary mb-10">
              Credit tiers &amp; limits
            </Reveal>
            <Reveal className="float-card p-6 md:p-8">
              <div className="font-sans text-sm font-semibold text-text-secondary uppercase tracking-wide border-b border-border pb-4 mb-6">
                Credit limit by reputation tier (V2)
              </div>
              <div className="space-y-3">
                {TIERS.map((row) => (
                  <div
                    key={row.label}
                    className={[
                      "flex items-center justify-between py-3 px-4 rounded-xl transition-colors",
                      row.featured ? "bg-accent-dim border border-accent/25" : "border border-transparent",
                    ].join(" ")}
                  >
                    <div>
                      <div className="font-sans font-semibold text-sm text-text-primary flex items-center gap-2">
                        {row.label}
                        {row.featured && (
                          <span className="font-pixel text-[9px] uppercase px-2 py-0.5 rounded-full bg-brand-gradient text-white">Popular</span>
                        )}
                      </div>
                      <div className="font-sans text-xs text-text-muted">{row.sub}</div>
                    </div>
                    <span className="font-pixel text-sm font-bold px-3 py-1.5 rounded-full bg-elevated-2 text-accent-hover">
                      {row.formula}
                    </span>
                  </div>
                ))}
              </div>
            </Reveal>

            <Reveal className="mt-8 flex gap-4 glass-panel-danger glass-panel p-4">
              <ShieldAlert size={20} className="text-danger shrink-0" strokeWidth={2} />
              <p className="font-body text-sm font-medium text-danger leading-relaxed">
                Slashing is strict: miss 30 rounds of payment and anyone can liquidate your stake.
              </p>
            </Reveal>
          </div>
        </div>
      </section>

      {/* ── TESTIMONIALS ── */}
      <section className="relative py-20 px-4">
        <div className="max-w-[1040px] mx-auto">
          <Reveal className="mb-14 flex flex-col items-center text-center">
            <h2 className="font-display font-bold text-3xl md:text-4xl text-text-primary">
              Built alongside early integrators
            </h2>
            <p className="font-body text-base text-text-muted mt-3 max-w-md">
              Illustrative feedback from the protocol's testing phase.
            </p>
          </Reveal>
          <motion.div
            variants={stagger}
            initial="hidden"
            whileInView="show"
            viewport={{ once: true, margin: "-60px" }}
            className="grid grid-cols-1 md:grid-cols-3 gap-6"
          >
            {TESTIMONIALS.map((t) => <TestimonialCard key={t.name} {...t} />)}
          </motion.div>
        </div>
      </section>

      {/* ── FAQ ── */}
      <section className="relative py-20 px-4">
        <div className="max-w-[720px] mx-auto">
          <Reveal className="mb-12 flex flex-col items-center text-center">
            <h2 className="font-display font-bold text-3xl md:text-4xl text-text-primary">
              Frequently asked
            </h2>
          </Reveal>
          <div className="flex flex-col gap-3">
            {FAQS.map((f, i) => (
              <FaqItem
                key={f.q}
                q={f.q}
                a={f.a}
                isOpen={openFaq === i}
                onToggle={() => setOpenFaq(openFaq === i ? -1 : i)}
              />
            ))}
          </div>
        </div>
      </section>

      {/* ── NETWORK PROOF ── */}
      <section className="relative py-20 px-4">
        <div className="max-w-[900px] mx-auto flex flex-col items-center text-center">
          <Reveal className="badge-chip badge-accent mb-10">
            <span className="font-pixel text-xs font-bold uppercase tracking-widest flex items-center gap-2">
              <Radio size={12} strokeWidth={2.5} /> Algorand Testnet
            </span>
          </Reveal>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-5 w-full mb-10">
            <Reveal className="float-card p-6 flex flex-col items-center">
              <span className="font-sans text-sm font-medium text-text-secondary mb-1">App ID</span>
              <span className="font-pixel text-xl font-bold text-text-primary">768682767</span>
            </Reveal>
            <Reveal className="float-card p-6 flex flex-col items-center">
              <span className="font-sans text-sm font-medium text-text-secondary mb-1">Network</span>
              <span className="font-pixel text-lg font-bold text-text-primary">Algorand Testnet</span>
            </Reveal>
            <Reveal className="float-card p-6 flex flex-col items-center">
              <span className="font-sans text-sm font-medium text-text-secondary mb-1">Contract</span>
              <span className="font-pixel text-lg font-bold text-text-primary">ARC-4 · Puya</span>
            </Reveal>
          </div>

          <a
            href="https://developer.algorand.org/docs/get-details/dapps/smart-contracts/"
            target="_blank"
            rel="noopener noreferrer"
            className="px-6 py-2.5 rounded-full glass-panel !shadow-soft-sm font-display font-semibold text-sm text-text-primary hover:!shadow-soft-md transition-all"
          >
            Learn about verifying on-chain →
          </a>
        </div>
      </section>

      {/* ── CTA ── */}
      <section className="relative py-24 px-4">
        <Reveal className="max-w-[720px] mx-auto text-center flex flex-col items-center float-card p-12 md:p-16">
          <h2 className="font-display font-bold text-4xl md:text-5xl text-text-primary mb-6">
            Ready to <span className="gradient-text">get started?</span>
          </h2>
          <p className="font-body text-lg text-text-secondary mb-10 max-w-md">
            Build reputation in a trustless ecosystem. Give your agents the capital they deserve.
          </p>
          <motion.button
            whileHover={{ y: -3, scale: 1.02 }}
            whileTap={{ y: 0, scale: 0.98 }}
            transition={{ type: "spring", stiffness: 400, damping: 25 }}
            onClick={onLaunchApp}
            className="w-full sm:w-auto h-16 px-12 rounded-full bg-brand-gradient text-white shadow-soft-lg font-display font-semibold text-xl"
          >
            Launch Terminal
          </motion.button>
        </Reveal>
      </section>

      {/* ── FOOTER ── */}
      <footer className="relative pt-8 px-4 border-t border-border">
        <div className="max-w-[1040px] mx-auto flex flex-col sm:flex-row items-center justify-between gap-4">
          <span className="font-display font-semibold text-sm text-text-muted">© Trestle Protocol</span>
          <div className="flex items-center gap-6">
            <a href="#" className="font-body text-sm text-text-muted hover:text-text-primary transition-colors">Docs</a>
            <a
              href={`https://testnet.explorer.perawallet.app/application/${APP_ID}/`}
              target="_blank" rel="noopener noreferrer"
              className="font-body text-sm text-text-muted hover:text-text-primary transition-colors"
            >
              Explorer
            </a>
            <a href="https://github.com" target="_blank" rel="noopener noreferrer" className="font-body text-sm text-text-muted hover:text-text-primary transition-colors">GitHub</a>
          </div>
        </div>
      </footer>
    </div>
  );
}
