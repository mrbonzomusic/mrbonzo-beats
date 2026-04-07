import { c as createComponent, r as renderTemplate, d as defineScriptVars, a as renderSlot, b as addAttribute, e as renderHead, f as createAstro, m as maybeRenderHead, g as renderComponent } from '../chunks/astro/server_DiVmB41q.mjs';
import 'piccolore';
import 'html-escaper';
import 'clsx';
/* empty css                                 */
export { renderers } from '../renderers.mjs';

const en = {
  nav: {
    home: "Home",
    beats: "Beats",
    player: "Player",
    spotify: "Spotify",
    youtube: "YouTube",
    tiktok: "TikTok",
    store: "Store"
  },
  hero: {
    label: "Beatmaker Portfolio",
    subtitle: "Dark, modern, and aggressive type beats built for artists who want energy and edge.",
    browse: "Browse Beats",
    featured: "Featured Player"
  },
  playlists: {
    title: "YouTube Playlists",
    viewAll: "View All",
    open: "Open",
    shop: "Shop on Beatstars"
  },
  about: {
    label: "About Mr. Bonzo",
    title: "The Architect of Energy",
    bio: "Alexandros Pilatos is a music producer/audio engineer in Athens, active since 2003. Founder of Purple Sound Studio (2007). His signature sound blends Boom Bap, Lofi, Trap, Dnb, Reggae, Breakbeat, Electronica, and Progressive House.",
    contact: "Contact for Customs",
    beatmaker: "Beatmaker",
    engineer: "Studio Engineer",
    producer: "Audio Producer"
  },
  collaborations: {
    title: "Collaborations",
    subtitle: "Artists and projects developed through Purple Sound Studio."
  },
  releases: {
    title: "Official Releases",
    follow: "Follow on Spotify",
    listen: "Listen on Spotify",
    statusLive: "Spotify API: Live Data",
    statusFallback: "Spotify API: Fallback Data",
    statusError: "Spotify API: Error (Fallback Data)"
  },
  services: {
    title: "Professional Services",
    subtitle: "Built for artists, labels, and audiovisual projects."
  },
  footer: {
    rights: "All rights reserved.",
    instagram: "Instagram (@mrbonzobeats)"
  }
};

const el = {
  nav: {
    home: "Αρχική",
    beats: "Beats",
    player: "Player",
    spotify: "Spotify",
    youtube: "YouTube",
    tiktok: "TikTok",
    store: "Store"
  },
  hero: {
    label: "Πορτφόλιο Beatmaker",
    subtitle: "Σκοτεινά, μοντέρνα και επιθετικά type beats για artists που θέλουν ένταση και χαρακτήρα.",
    browse: "Άκου Beats",
    featured: "Featured Player"
  },
  playlists: {
    title: "YouTube Playlists",
    viewAll: "Όλα",
    open: "Άνοιγμα",
    shop: "Shop on Beatstars"
  },
  about: {
    label: "Σχετικά με τον Mr. Bonzo",
    title: "Ο Αρχιτέκτονας της Ενέργειας",
    bio: "Ο Αλέξανδρος Πιλάτος είναι music producer και audio engineer στην Αθήνα, ενεργός από το 2003. Είναι ο ιδρυτής του Purple Sound Studio (2007). Ο ήχος του συνδυάζει Boom Bap, Lofi, Trap, Dnb, Reggae, Breakbeat, Electronica και Progressive House.",
    contact: "Επικοινωνία για Customs",
    beatmaker: "Beatmaker",
    engineer: "Studio Engineer",
    producer: "Audio Producer"
  },
  collaborations: {
    title: "Συνεργασίες",
    subtitle: "Καλλιτέχνες και projects που αναπτύχθηκαν μέσω του Purple Sound Studio."
  },
  releases: {
    title: "Επίσημες Κυκλοφορίες",
    follow: "Follow on Spotify",
    listen: "Ακρόαση στο Spotify",
    statusLive: "Spotify API: Live Data",
    statusFallback: "Spotify API: Fallback Data",
    statusError: "Spotify API: Error (Fallback Data)"
  },
  services: {
    title: "Επαγγελματικές Υπηρεσίες",
    subtitle: "Για artists, labels και audiovisual projects."
  },
  footer: {
    rights: "Με επιφύλαξη παντός δικαιώματος.",
    instagram: "Instagram (@mrbonzobeats)"
  }
};

const socialLinks = {
  spotify: "https://open.spotify.com/artist/5ziH2Z9Gl3M1FhcYvrLHpv?si=8IBQNsfQS7yWfIO_DFF-9w",
  youtube: "https://www.youtube.com/@mrbonzobeatz",
  tiktok: "https://www.tiktok.com/@mr.bonzobeats",
  instagram: "https://www.instagram.com/mrbonzobeatz/",
  email: "mailto:mrbonzomusic@gmail.com"
};
const beatstarsLinks = {
  profile: "https://www.beatstars.com/mrbonzobeats",
  player: "https://player.beatstars.com/?storeId=133234"
};

var __freeze = Object.freeze;
var __defProp = Object.defineProperty;
var __template = (cooked, raw) => __freeze(__defProp(cooked, "raw", { value: __freeze(cooked.slice()) }));
var _a;
const $$Astro$1 = createAstro();
const $$BaseLayout = createComponent(($$result, $$props, $$slots) => {
  const Astro2 = $$result.createAstro($$Astro$1, $$props, $$slots);
  Astro2.self = $$BaseLayout;
  const { title = "Mr. Bonzo | Type Beats" } = Astro2.props;
  const logoPath = "/images/mrBonzo-logo-variations-2%20transparent-Icon.png";
  const i18nPayload = { en, el };
  return renderTemplate(_a || (_a = __template(['<html lang="en"> <head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><meta name="description" content="Mr. Bonzo beatmaker portfolio featuring type beats, a Beatstars showcase, and social links."><title>', "</title>", '</head> <body class="min-h-screen antialiased"> <main class="mx-auto max-w-7xl px-6 pb-16 pt-8 sm:px-10 lg:px-16"> <header class="sticky top-0 z-50 mb-12"> <div class="rounded-2xl border border-fuchsia-500/25 bg-black/70 px-4 py-4 backdrop-blur-md sm:px-6"> <div class="flex flex-wrap items-center justify-center gap-x-8 gap-y-3 md:justify-between"> <nav class="order-3 hidden items-center justify-center gap-4 text-[10px] font-semibold uppercase tracking-[0.16em] text-fuchsia-200 md:order-1 md:flex md:w-auto lg:gap-5 lg:text-[11px] lg:tracking-[0.18em]"> <a href="/" class="transition hover:text-fuchsia-300" data-i18n="nav.home">Home</a> <a href="#beats" class="transition hover:text-fuchsia-300" data-i18n="nav.beats">Beats</a> <a href="#beatstars" class="transition hover:text-fuchsia-300" data-i18n="nav.player">Player</a> </nav> <a href="/" class="order-1 inline-flex w-full items-center justify-center md:order-2 md:w-auto"> <img', ' alt="Mr. Bonzo logo" class="h-[66px] w-auto max-w-[210px] drop-shadow-[0_0_26px_rgba(217,70,239,0.95)] md:h-[56px] md:max-w-[170px] lg:h-[72px] lg:max-w-[220px]"> </a> <nav class="order-2 flex w-full items-center justify-center gap-5 pt-1 md:order-3 md:w-auto md:justify-end md:gap-4 md:pt-0 lg:gap-7" aria-label="Social links"> <a', ' target="_blank" rel="noopener noreferrer" class="text-[11px] font-black uppercase tracking-[0.16em] text-fuchsia-200 transition duration-200 hover:text-fuchsia-300 hover:drop-shadow-[0_0_10px_rgba(217,70,239,0.75)] lg:text-xs lg:tracking-[0.2em]" aria-label="Spotify" title="Spotify" data-i18n="nav.spotify">\nSpotify\n</a> <a', ' target="_blank" rel="noopener noreferrer" class="text-[11px] font-black uppercase tracking-[0.16em] text-fuchsia-200 transition duration-200 hover:text-fuchsia-300 hover:drop-shadow-[0_0_10px_rgba(217,70,239,0.75)] lg:text-xs lg:tracking-[0.2em]" aria-label="YouTube" title="YouTube" data-i18n="nav.youtube">\nYouTube\n</a> <a', ' target="_blank" rel="noopener noreferrer" class="text-[11px] font-black uppercase tracking-[0.16em] text-fuchsia-200 transition duration-200 hover:text-fuchsia-300 hover:drop-shadow-[0_0_10px_rgba(217,70,239,0.75)] lg:text-xs lg:tracking-[0.2em]" aria-label="TikTok" title="TikTok" data-i18n="nav.tiktok">\nTikTok\n</a> <a', ' target="_blank" rel="noopener noreferrer" class="text-[11px] font-black uppercase tracking-[0.16em] text-fuchsia-200 transition duration-200 hover:text-fuchsia-300 hover:drop-shadow-[0_0_10px_rgba(217,70,239,0.75)] lg:text-xs lg:tracking-[0.2em]" aria-label="Store" title="Store" data-i18n="nav.store">\nStore\n</a> <div class="ml-1 flex items-center gap-2 text-[11px] font-black uppercase tracking-[0.16em] lg:text-xs lg:tracking-[0.2em]"> <button type="button" data-lang-switch="en" class="rounded px-1 text-fuchsia-200 transition hover:text-fuchsia-300 data-[active=true]:text-fuchsia-300 data-[active=true]:drop-shadow-[0_0_10px_rgba(217,70,239,0.75)]">\nEN\n</button> <span class="text-fuchsia-500/70">|</span> <button type="button" data-lang-switch="el" class="rounded px-1 text-fuchsia-200 transition hover:text-fuchsia-300 data-[active=true]:text-fuchsia-300 data-[active=true]:drop-shadow-[0_0_10px_rgba(217,70,239,0.75)]">\nEL\n</button> </div> </nav> </div> </div> </header> ', " </main> <script>(function(){", '\n      const dictionaries = i18nPayload;\n      const getByPath = (obj, path) => path.split(".").reduce((acc, key) => (acc ? acc[key] : undefined), obj);\n\n      const applyLanguage = (lang) => {\n        const dict = dictionaries[lang] || dictionaries.en;\n        document.documentElement.lang = lang;\n        localStorage.setItem("site-lang", lang);\n\n        document.querySelectorAll("[data-i18n]").forEach((node) => {\n          const key = node.getAttribute("data-i18n");\n          const value = key ? getByPath(dict, key) : null;\n          if (typeof value === "string") node.textContent = value;\n        });\n\n        document.querySelectorAll("[data-i18n-status]").forEach((node) => {\n          const status = node.getAttribute("data-i18n-status");\n          const key =\n            status === "live" ? "releases.statusLive" : status === "error" ? "releases.statusError" : "releases.statusFallback";\n          const value = getByPath(dict, key);\n          if (typeof value === "string") node.textContent = value;\n        });\n\n        document.querySelectorAll("[data-lang-switch]").forEach((btn) => {\n          const isActive = btn.getAttribute("data-lang-switch") === lang;\n          btn.setAttribute("data-active", isActive ? "true" : "false");\n          btn.setAttribute("aria-pressed", isActive ? "true" : "false");\n        });\n      };\n\n      const initial = localStorage.getItem("site-lang") || "en";\n      applyLanguage(initial);\n      document.querySelectorAll("[data-lang-switch]").forEach((btn) => {\n        btn.addEventListener("click", () => applyLanguage(btn.getAttribute("data-lang-switch") || "en"));\n      });\n    })();<\/script> </body> </html>'])), title, renderHead(), addAttribute(logoPath, "src"), addAttribute(socialLinks.spotify, "href"), addAttribute(socialLinks.youtube, "href"), addAttribute(socialLinks.tiktok, "href"), addAttribute(beatstarsLinks.profile, "href"), renderSlot($$result, $$slots["default"]), defineScriptVars({ i18nPayload }));
}, "H:/User/Documents/Mr. Bonzo Beats Site/src/layouts/BaseLayout.astro", void 0);

const aboutContent = {
  en: {
    bio: "Alexandros Pilatos is a music producer/audio engineer in Athens, active since 2003. Founder of Purple Sound Studio (2007). His signature sound blends Boom Bap, Lofi, Trap, Dnb, Reggae, Breakbeat, Electronica, and Progressive House."
  }};

const $$AboutSection = createComponent(($$result, $$props, $$slots) => {
  return renderTemplate`${maybeRenderHead()}<section id="about" class="relative mt-16 overflow-hidden rounded-3xl border border-fuchsia-500/30 bg-black"> <div class="absolute inset-0 bg-[radial-gradient(circle_at_10%_20%,rgba(168,85,247,0.18),transparent_40%),radial-gradient(circle_at_80%_70%,rgba(217,70,239,0.14),transparent_45%)]"></div> <div class="relative grid items-stretch gap-0 lg:grid-cols-[1.05fr_1fr]"> <div class="relative min-h-[320px] lg:min-h-[460px]"> <img src="/images/Mr.%20Bonzo%20half%20face.jpg" alt="Mr. Bonzo portrait" class="h-full w-full object-cover object-center" loading="lazy"> <div class="pointer-events-none absolute inset-y-0 right-0 hidden w-28 bg-gradient-to-r from-transparent to-black lg:block"></div> <div class="pointer-events-none absolute inset-x-0 bottom-0 h-20 bg-gradient-to-b from-transparent to-black lg:hidden"></div> </div> <div class="flex flex-col justify-center px-6 py-10 text-center sm:px-10 lg:px-12 lg:text-left"> <p class="text-xs font-semibold uppercase tracking-[0.22em] text-fuchsia-300/85" data-i18n="about.label">About Mr. Bonzo</p> <h2 class="mt-3 text-3xl font-black uppercase tracking-tight text-white sm:text-4xl lg:text-5xl"> <span data-i18n="about.title">The Architect of Energy</span> </h2> <p class="mt-5 text-sm leading-relaxed text-purple-100/85 sm:text-base" data-i18n="about.bio"> ${aboutContent.en.bio} </p> <div class="mt-6 flex flex-wrap justify-center gap-2 lg:justify-start"> <span class="rounded-full border border-fuchsia-500/40 px-3 py-1 text-xs font-semibold uppercase tracking-wide text-fuchsia-200" data-i18n="about.beatmaker">Beatmaker</span> <span class="rounded-full border border-fuchsia-500/40 px-3 py-1 text-xs font-semibold uppercase tracking-wide text-fuchsia-200" data-i18n="about.engineer">Studio Engineer</span> <span class="rounded-full border border-fuchsia-500/40 px-3 py-1 text-xs font-semibold uppercase tracking-wide text-fuchsia-200" data-i18n="about.producer">Audio Producer</span> </div> <div class="mt-8"> <a${addAttribute(socialLinks.instagram, "href")} target="_blank" rel="noopener noreferrer" class="inline-flex rounded-full border border-fuchsia-400/70 bg-fuchsia-600/90 px-6 py-3 text-xs font-black uppercase tracking-[0.2em] text-white shadow-[0_0_20px_rgba(217,70,239,0.5)] transition hover:bg-fuchsia-500" data-i18n="about.contact">
Contact for Customs
</a> </div> </div> </div> </section>`;
}, "H:/User/Documents/Mr. Bonzo Beats Site/src/components/AboutSection.astro", void 0);

const collaborators = [
  "Thanasimos",
  "Saske",
  "ΔΠΘ",
  "Xplicit",
  "Eksokosmikos",
  "Phyrosun",
  "Mista Blackouts",
  "Τωμ Unit",
  "TkTzikso",
  "Dilitirio",
  "Rocklee",
  "Underground Company",
  "Logos Timis",
  "Elefthero Pnevma"
];

const $$CollaborationsSection = createComponent(($$result, $$props, $$slots) => {
  const marquee = [...collaborators, ...collaborators];
  return renderTemplate`${maybeRenderHead()}<section id="collaborations" class="relative mt-16 overflow-hidden rounded-3xl border border-fuchsia-500/30 bg-black/80 px-6 py-8 sm:px-10" data-astro-cid-eme4bpq7> <div class="absolute inset-0 bg-[radial-gradient(circle_at_0%_50%,rgba(168,85,247,0.14),transparent_35%),radial-gradient(circle_at_100%_50%,rgba(217,70,239,0.12),transparent_35%)]" data-astro-cid-eme4bpq7></div> <div class="relative overflow-hidden" data-astro-cid-eme4bpq7> <h3 class="text-2xl font-black uppercase tracking-tight text-white sm:text-3xl" data-i18n="collaborations.title" data-astro-cid-eme4bpq7>Collaborations</h3> <p class="mt-2 text-sm text-purple-100/75" data-i18n="collaborations.subtitle" data-astro-cid-eme4bpq7>Artists and projects developed through Purple Sound Studio.</p> <div class="mt-6 marquee-track" data-astro-cid-eme4bpq7> <div class="marquee-content" data-astro-cid-eme4bpq7> ${marquee.map((artist, idx) => renderTemplate`<span class="inline-flex items-center text-sm font-bold uppercase tracking-[0.18em] text-fuchsia-200 sm:text-base" data-astro-cid-eme4bpq7> ${artist} ${idx < marquee.length - 1 && renderTemplate`<span class="mx-5 text-fuchsia-400/80" data-astro-cid-eme4bpq7>✦</span>`} </span>`)} </div> </div> </div> </section> `;
}, "H:/User/Documents/Mr. Bonzo Beats Site/src/components/CollaborationsSection.astro", void 0);

const $$Astro = createAstro();
const $$DiscographySection = createComponent(($$result, $$props, $$slots) => {
  const Astro2 = $$result.createAstro($$Astro, $$props, $$slots);
  Astro2.self = $$DiscographySection;
  const fallbackReleases = [
    {
      title: "Deciduous EP",
      year: "2024",
      cover: "/images/Mr.%20Bonzo%20half%20face.jpg",
      spotify: "https://open.spotify.com/artist/5ziH2Z9Gl3M1FhcYvrLHpv?si=8IBQNsfQS7yWfIO_DFF-9w"
    }
  ];
  const { releases = fallbackReleases, status = "fallback" } = Astro2.props;
  const spotifyUrl = socialLinks.spotify;
  const statusLabel = status === "live" ? "Spotify API: Live Data" : status === "error" ? "Spotify API: Error (Fallback Data)" : "Spotify API: Fallback Data";
  return renderTemplate`${maybeRenderHead()}<section id="releases" class="mt-16"> <div class="mb-6 flex flex-wrap items-end justify-between gap-4"> <div> <h3 class="text-3xl font-black uppercase tracking-tight text-white sm:text-4xl" data-i18n="releases.title">Official Releases</h3> <p class="mt-2 text-[11px] font-bold uppercase tracking-[0.16em] text-fuchsia-300/85"${addAttribute(status, "data-i18n-status")}>${statusLabel}</p> </div> <a${addAttribute(spotifyUrl, "href")} target="_blank" rel="noopener noreferrer" class="rounded-full border border-fuchsia-400/70 bg-fuchsia-600/90 px-5 py-2 text-[11px] font-black uppercase tracking-[0.18em] text-white shadow-[0_0_14px_rgba(217,70,239,0.45)] transition hover:bg-fuchsia-500" data-i18n="releases.follow">
Follow on Spotify
</a> </div> <div class="grid gap-4 sm:grid-cols-2 lg:grid-cols-3"> ${releases.map((release) => renderTemplate`<article class="group overflow-hidden rounded-2xl border border-fuchsia-500/25 bg-black/80 transition hover:border-fuchsia-400/55"> <img${addAttribute(release.cover, "src")}${addAttribute(`${release.title} cover`, "alt")} loading="lazy" class="aspect-square w-full object-cover"> <div class="p-4"> <h4 class="text-lg font-black uppercase tracking-wide text-white">${release.title}</h4> <p class="mt-1 text-xs font-bold uppercase tracking-[0.2em] text-fuchsia-300/90">${release.year}</p> <a${addAttribute(release.spotify, "href")} target="_blank" rel="noopener noreferrer" class="mt-4 inline-flex rounded-full border border-fuchsia-500/55 px-4 py-2 text-[11px] font-black uppercase tracking-[0.18em] text-fuchsia-200 transition hover:border-fuchsia-300 hover:text-fuchsia-100" data-i18n="releases.listen">
Listen on Spotify
</a> </div> </article>`)} </div> </section>`;
}, "H:/User/Documents/Mr. Bonzo Beats Site/src/components/DiscographySection.astro", void 0);

const $$FeaturedBeatstars = createComponent(($$result, $$props, $$slots) => {
  return renderTemplate`${maybeRenderHead()}<section id="beatstars" class="mt-16 scroll-mt-36"> <div class="overflow-hidden rounded-3xl border border-fuchsia-500/50 bg-black p-2 shadow-xl shadow-fuchsia-900/30"> <iframe${addAttribute(beatstarsLinks.player, "src")} width="100%" height="800" title="Mr. Bonzo Beatstars Player" loading="lazy">
      -- none --
    </iframe> </div> </section>`;
}, "H:/User/Documents/Mr. Bonzo Beats Site/src/components/FeaturedBeatstars.astro", void 0);

const $$Hero = createComponent(($$result, $$props, $$slots) => {
  return renderTemplate`${maybeRenderHead()}<section class="relative overflow-hidden rounded-3xl border border-fuchsia-500/50 bg-black px-8 py-16 shadow-2xl shadow-fuchsia-700/25 sm:px-12 sm:py-24"> <div class="absolute inset-0 bg-[radial-gradient(circle_at_top,_rgba(217,70,239,0.25),_transparent_55%)]"></div> <div class="relative"> <p class="mb-4 text-sm uppercase tracking-[0.3em] text-purple-300/80" data-i18n="hero.label">Beatmaker Portfolio</p> <h1 class="text-5xl font-black uppercase tracking-tight text-white sm:text-7xl lg:text-8xl">Mr. Bonzo Beats</h1> <p class="mt-6 max-w-2xl text-base text-purple-100/80 sm:text-lg" data-i18n="hero.subtitle">
Dark, modern, and aggressive type beats built for artists who want energy and edge.
</p> <div class="mt-8 flex flex-wrap gap-4"> <a href="#beatstars" class="rounded-full border border-fuchsia-400/70 bg-fuchsia-600/90 px-6 py-3 text-sm font-semibold uppercase tracking-wide text-white shadow-[0_0_24px_rgba(217,70,239,0.5)] transition hover:bg-fuchsia-500" data-i18n="hero.browse">
Browse Beats
</a> <a href="#beatstars" class="rounded-full border border-purple-500/40 bg-black/50 px-6 py-3 text-sm font-semibold uppercase tracking-wide text-purple-100 transition hover:border-purple-300" data-i18n="hero.featured">
Featured Player
</a> </div> </div> </section>`;
}, "H:/User/Documents/Mr. Bonzo Beats Site/src/components/Hero.astro", void 0);

const $$ServicesSection = createComponent(($$result, $$props, $$slots) => {
  return renderTemplate`${maybeRenderHead()}<section id="services" class="mt-16 rounded-3xl border border-fuchsia-500/30 bg-black/85 p-6 sm:p-8"> <h3 class="text-3xl font-black uppercase tracking-tight text-white sm:text-4xl" data-i18n="services.title">Professional Services</h3> <p class="mt-2 text-sm text-purple-100/75" data-i18n="services.subtitle">Built for artists, labels, and audiovisual projects.</p> <div class="mt-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-3"> <div class="rounded-xl border border-fuchsia-500/25 bg-black px-4 py-4 text-sm font-bold uppercase tracking-[0.14em] text-fuchsia-100">Music Production</div> <div class="rounded-xl border border-fuchsia-500/25 bg-black px-4 py-4 text-sm font-bold uppercase tracking-[0.14em] text-fuchsia-100">Recording</div> <div class="rounded-xl border border-fuchsia-500/25 bg-black px-4 py-4 text-sm font-bold uppercase tracking-[0.14em] text-fuchsia-100">Mixing &amp; Mastering</div> <div class="rounded-xl border border-fuchsia-500/25 bg-black px-4 py-4 text-sm font-bold uppercase tracking-[0.14em] text-fuchsia-100">Sound Design</div> <div class="rounded-xl border border-fuchsia-500/25 bg-black px-4 py-4 text-sm font-bold uppercase tracking-[0.14em] text-fuchsia-100">Scoring for Media</div> </div> </section>`;
}, "H:/User/Documents/Mr. Bonzo Beats Site/src/components/ServicesSection.astro", void 0);

const $$SiteFooter = createComponent(($$result, $$props, $$slots) => {
  return renderTemplate`${maybeRenderHead()}<footer id="contact" class="mt-20 border-t border-purple-700/25 pt-8"> <div class="flex flex-col gap-4 text-center sm:flex-row sm:items-center sm:justify-between sm:text-left"> <p class="text-xs uppercase tracking-[0.2em] text-purple-300/75">
Copyright © ${(/* @__PURE__ */ new Date()).getFullYear()} Mr. Bonzo. <span data-i18n="footer.rights">All rights reserved.</span> </p> <div class="flex flex-wrap items-center justify-center gap-5 sm:justify-end"> <a${addAttribute(socialLinks.instagram, "href")} target="_blank" rel="noopener noreferrer" class="text-xs font-bold uppercase tracking-[0.2em] text-fuchsia-200 transition hover:text-fuchsia-300" data-i18n="footer.instagram">
Instagram (@mrbonzobeats)
</a> <a${addAttribute(socialLinks.youtube, "href")} target="_blank" rel="noopener noreferrer" class="text-xs font-bold uppercase tracking-[0.2em] text-fuchsia-200 transition hover:text-fuchsia-300" data-i18n="nav.youtube">
YouTube
</a> <a${addAttribute(socialLinks.email, "href")} class="text-xs font-bold uppercase tracking-[0.2em] text-fuchsia-200 transition hover:text-fuchsia-300">
mrbonzomusic@gmail.com
</a> </div> </div> </footer>`;
}, "H:/User/Documents/Mr. Bonzo Beats Site/src/components/SiteFooter.astro", void 0);

const $$TypeBeatGrid = createComponent(($$result, $$props, $$slots) => {
  const channelPlaylistsUrl = "https://www.youtube.com/@mrbonzobeatz/playlists";
  const playlists = [
    {
      title: "Boom Bap Beats",
      href: "https://www.youtube.com/watch?v=7j096H_mMnc&list=PLMdNnt6p6RrEdkjzDdS12hUJNx8ENBul6",
      image: "/images/Boom%20Bap%20Beats.png",
      beatstarsHref: "https://www.beatstars.com/playlists/5350129"
    },
    {
      title: "Trap Beats",
      href: "https://www.youtube.com/watch?v=b6-ThC1GU2Q&list=PLMdNnt6p6RrEotLVDWzYhCLVH_fG3kn93",
      image: "/images/Trap%20Beats.png",
      beatstarsHref: "https://www.beatstars.com/playlists/5319147"
    },
    {
      title: "Free Beats",
      href: "https://www.youtube.com/watch?v=kPGXHFoG4LI&list=PLMdNnt6p6RrEt5bZVQd1bZZ21DUj7LvyW",
      image: "/images/Free%20Beats.png",
      beatstarsHref: "https://www.beatstars.com/playlists/6148560"
    }
  ];
  return renderTemplate`${maybeRenderHead()}<section id="beats" class="mt-16"> <div class="mb-6 flex items-end justify-between gap-4"> <h2 class="text-3xl font-extrabold uppercase tracking-tight text-white sm:text-4xl" data-i18n="playlists.title">YouTube Playlists</h2> <a${addAttribute(channelPlaylistsUrl, "href")} target="_blank" rel="noopener noreferrer" class="text-sm font-medium uppercase tracking-wide text-fuchsia-300 hover:text-fuchsia-200" data-i18n="playlists.viewAll">
View All
</a> </div> <div class="grid gap-5 sm:grid-cols-2 lg:grid-cols-3"> ${playlists.map((playlist) => renderTemplate`<article class="group rounded-2xl border border-fuchsia-500/30 bg-black p-4 shadow-[0_0_24px_rgba(192,38,211,0.15)] transition hover:-translate-y-1 hover:border-fuchsia-400/70"> <div class="relative aspect-video overflow-hidden rounded-xl border border-fuchsia-500/40 bg-black"> <img${addAttribute(playlist.image, "src")}${addAttribute(playlist.title, "alt")} class="h-full w-full object-cover transition duration-300 group-hover:scale-105" loading="lazy"> <div class="absolute inset-0 bg-gradient-to-t from-black/85 via-black/35 to-black/30"></div> <h3 class="absolute bottom-3 left-3 right-3 text-base font-black uppercase tracking-[0.12em] text-white"> ${playlist.title} </h3> </div> <div class="mt-4 flex items-center gap-3"> <a${addAttribute(playlist.href, "href")} target="_blank" rel="noopener noreferrer" class="inline-flex rounded-full border border-fuchsia-500/55 px-4 py-2 text-[11px] font-black uppercase tracking-[0.18em] text-fuchsia-200 transition hover:border-fuchsia-300 hover:text-fuchsia-100" data-i18n="playlists.open">
Open
</a> <a${addAttribute(playlist.beatstarsHref, "href")} target="_blank" rel="noopener noreferrer" class="inline-flex rounded-full border border-fuchsia-400/70 bg-fuchsia-600/85 px-4 py-2 text-[11px] font-black uppercase tracking-[0.18em] text-white shadow-[0_0_14px_rgba(217,70,239,0.45)] transition hover:bg-fuchsia-500" data-i18n="playlists.shop">
Shop on Beatstars
</a> </div> </article>`)} </div> </section>`;
}, "H:/User/Documents/Mr. Bonzo Beats Site/src/components/TypeBeatGrid.astro", void 0);

const client_id = "e8bb1bd8c7544e62aa13560978257908";
const client_secret = "6ab02fb7278d4c3990c838d063ab7615";
const artist_id = "5ziH2Z9Gl3M1FhcYvrLHpv";
async function getAccessToken() {
  try {
    const response = await fetch("https://accounts.spotify.com/api/token", {
      method: "POST",
      headers: {
        "Authorization": "Basic " + btoa(client_id + ":" + client_secret),
        "Content-Type": "application/x-www-form-urlencoded"
      },
      body: "grant_type=client_credentials"
    });
    const data = await response.json();
    return data.access_token;
  } catch (error) {
    console.error("Spotify Auth Error:", error);
    return null;
  }
}
async function getArtistAlbums() {
  try {
    const access_token = await getAccessToken();
    if (!access_token) return [];
    const response = await fetch(
      `https://api.spotify.com/v1/artists/${artist_id}/albums?include_groups=album,single&limit=20&market=GR`,
      {
        headers: { "Authorization": `Bearer ${access_token}` }
      }
    );
    const data = await response.json();
    if (!data.items) return [];
    const seen = /* @__PURE__ */ new Set();
    return data.items.filter((item) => {
      const itemName = item.name.toLowerCase();
      const isDuplicate = seen.has(itemName);
      seen.add(itemName);
      return !isDuplicate;
    });
  } catch (error) {
    console.error("Spotify Fetch Error:", error);
    return [];
  }
}

const $$Index = createComponent(async ($$result, $$props, $$slots) => {
  const fallbackReleases = [
    {
      title: "Deciduous EP",
      year: "2024",
      cover: "/images/Mr.%20Bonzo%20half%20face.jpg",
      spotify: "https://open.spotify.com/artist/5ziH2Z9Gl3M1FhcYvrLHpv?si=8IBQNsfQS7yWfIO_DFF-9w"
    },
    {
      title: "Rhythms Of Silence",
      year: "2020",
      cover: "/images/Mr.%20Bonzo%20Beats%20in%20the%20studio.jpg",
      spotify: "https://open.spotify.com/artist/5ziH2Z9Gl3M1FhcYvrLHpv?si=8IBQNsfQS7yWfIO_DFF-9w"
    },
    {
      title: "Blue Dream EP",
      year: "2018",
      cover: "/images/Mr.%20Bonzo%20half%20face.jpg",
      spotify: "https://open.spotify.com/artist/5ziH2Z9Gl3M1FhcYvrLHpv?si=8IBQNsfQS7yWfIO_DFF-9w"
    },
    {
      title: "B-Step Project EP",
      year: "2011",
      cover: "/images/Mr.%20Bonzo%20Beats%20in%20the%20studio.jpg",
      spotify: "https://open.spotify.com/artist/5ziH2Z9Gl3M1FhcYvrLHpv?si=8IBQNsfQS7yWfIO_DFF-9w"
    }
  ];
  const spotifyApiResult = await getArtistAlbums();
  const spotifyReleases = spotifyApiResult.releases.length ? spotifyApiResult.releases : fallbackReleases;
  const releasesStatus = spotifyApiResult.releases.length ? spotifyApiResult.status : "fallback";
  return renderTemplate`${renderComponent($$result, "BaseLayout", $$BaseLayout, { "title": "Mr. Bonzo | Beatmaker Portfolio" }, { "default": async ($$result2) => renderTemplate` ${renderComponent($$result2, "Hero", $$Hero, {})} ${renderComponent($$result2, "TypeBeatGrid", $$TypeBeatGrid, {})} ${renderComponent($$result2, "FeaturedBeatstars", $$FeaturedBeatstars, {})} ${renderComponent($$result2, "AboutSection", $$AboutSection, {})} ${renderComponent($$result2, "CollaborationsSection", $$CollaborationsSection, {})} ${renderComponent($$result2, "DiscographySection", $$DiscographySection, { "releases": spotifyReleases, "status": releasesStatus })} ${renderComponent($$result2, "ServicesSection", $$ServicesSection, {})} ${renderComponent($$result2, "SiteFooter", $$SiteFooter, {})} ` })}`;
}, "H:/User/Documents/Mr. Bonzo Beats Site/src/pages/index.astro", void 0);
const $$file = "H:/User/Documents/Mr. Bonzo Beats Site/src/pages/index.astro";
const $$url = "";

const _page = /*#__PURE__*/Object.freeze(/*#__PURE__*/Object.defineProperty({
  __proto__: null,
  default: $$Index,
  file: $$file,
  url: $$url
}, Symbol.toStringTag, { value: 'Module' }));

const page = () => _page;

export { page };
