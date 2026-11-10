export const privacyHtml = `
<h2>1. Who we are</h2>
<p>This Privacy Policy applies to the website <a href="https://mrbonzo.com/">https://mrbonzo.com</a> (and the Cloudflare Pages host <a href="https://mrbonzo-beats.pages.dev/">mrbonzo-beats.pages.dev</a>), related pages, and the operator tools we use to publish our own music content. The data controller is <strong>Alexandros Pilatos</strong>, trading as <strong>Mr. Bonzo</strong> and <strong>Purple Sound Studio</strong>, based in Athens, Greece. Contact: <a href="mailto:mrbonzomusic@gmail.com">mrbonzomusic@gmail.com</a>.</p>
<p>This policy is written to meet GDPR/EEA requirements and Google Cloud / YouTube API Services disclosure rules. It is not a substitute for independent legal advice.</p>

<h2>2. What this site and our tools do</h2>
<p>We offer:</p>
<ul>
<li>an official artist website with beats, drum kits, discography, contact, and language choice (English / Greek);</li>
<li>licensing and downloads fulfilled by third-party stores, mainly <a href="https://www.beatstars.com/mrbonzobeats">Beatstars</a> (and Pond5 for stock audio);</li>
<li>studio services (production, recording, mixing and mastering, sound design, scoring) arranged by enquiry;</li>
<li>optional newsletter signup (currently paused until the mailing system is publicly reachable);</li>
<li>internal publishing software (n8n workflows and a private uploader) that posts videos and related assets to channels we own, including YouTube, using Google APIs.</li>
</ul>

<h2>3. Data we collect on the website</h2>
<p>We collect as little as possible:</p>
<ul>
<li><strong>Language preference:</strong> stored in your browser as <code>localStorage['selected-lang']</code> (<code>en</code> or <code>el</code>). This does not identify you to us.</li>
<li><strong>Analytics:</strong> Google Analytics 4 (measurement ID G-XBS5WKEGPE) records approximate usage (pages, device/browser, coarse location, outbound clicks to stores and socials). GA uses Google cookies/identifiers. Google acts as processor; see <a href="https://policies.google.com/privacy" rel="noopener noreferrer" target="_blank">Google’s Privacy Policy</a>.</li>
<li><strong>Technical logs:</strong> Cloudflare may log IP address, user-agent, and request metadata to operate the CDN, DDoS protection, and TLS. Logs are retained according to Cloudflare’s policies.</li>
<li><strong>Contact:</strong> if you email us, message Discord, or write on Instagram, we receive whatever you send (name, handle, message, attachments such as receipts for claim clearance).</li>
<li><strong>Newsletter (when enabled):</strong> email address, signup time, and anti-spam honeypot fields. Stored in our self-hosted Plunk instance. Not sold. The public form is off until a stable API hostname exists.</li>
<li><strong>Purchases:</strong> Beatstars, PayPal, Pond5, and similar platforms process payments. We do not receive your full card data. We may see your store username, order ID, or a receipt you forward so we can whitelist a YouTube claim.</li>
</ul>
<p>We do not run a user account system on this website. We do not sell personal data.</p>

<h2>4. YouTube API Services (Google Cloud / n8n publisher)</h2>
<p>We operate a private publishing application (“Mr. Bonzo Studio Publisher”) built with n8n and related scripts. It uses <strong>YouTube Data API v3</strong> through a Google Cloud OAuth client to manage <em>our own</em> channels, including <a href="https://www.youtube.com/@mrbonzobeats">@mrbonzobeats</a> and <a href="https://www.youtube.com/@mrbonzomusic">@mrbonzomusic</a>.</p>
<p>By using any YouTube-powered feature of our services, you also agree to the <a href="https://www.youtube.com/t/terms" rel="noopener noreferrer" target="_blank">YouTube Terms of Service</a>. Information received from Google APIs is used in line with this Privacy Policy and the <a href="https://policies.google.com/privacy" rel="noopener noreferrer" target="_blank">Google Privacy Policy</a>.</p>
<p><strong>What the application accesses.</strong> With OAuth tokens issued to channels we control, the application may:</p>
<ul>
<li>upload, update, schedule, list, and delete videos (including Shorts);</li>
<li>read and write video titles, descriptions, tags, thumbnails, privacy status, and playlists;</li>
<li>read channel identity needed to confirm the authenticated channel;</li>
<li>refresh access tokens so scheduled jobs can run without a browser session.</li>
</ul>
<p><strong>What we do not do.</strong> The publisher is not a consumer login for visitors of mrbonzo.com. We do not use YouTube API data to build advertising profiles, sell or transfer YouTube user data to data brokers, or grant unrelated third parties independent access to YouTube API data. We do not use YouTube API data for purposes other than operating, securing, and improving the publishing of content on channels we own.</p>
<p><strong>Storage.</strong> Client ID, client secret, and refresh tokens are stored on private operator infrastructure (homelab / self-hosted n8n), not in the public website or in the browser of site visitors. Access tokens are short-lived and cached in memory where the uploader runs.</p>
<p><strong>Revocation.</strong> Access can be revoked at any time in Google Account permissions: <a href="https://myaccount.google.com/permissions" rel="noopener noreferrer" target="_blank">https://myaccount.google.com/permissions</a>. After revocation, refresh tokens stop working and uploads halt until re-authorised by the channel owner.</p>
<p>This use is intended to comply with the YouTube API Services Terms of Service, Developer Policies, and Limited Use requirements. If Google’s rules change, we will update this section.</p>

<h2>5. Other publishing platforms</h2>
<p>The same operator tools may post or delete content on Meta platforms (Facebook, Instagram, Stories) and similar channels we own, using tokens stored on the same private infrastructure. Those platforms’ own terms and privacy policies apply to data they process. Site visitors are not required to connect a Meta or Google account to browse mrbonzo.com.</p>

<h2>6. Cookies and similar technologies</h2>
<p>Strictly necessary: Cloudflare security and load balancing. Functional: language preference in localStorage (not a cookie). Analytics: Google Analytics cookies as described by Google. Third-party embeds (Beatstars player, YouTube if embedded) may set their own cookies. You can block analytics cookies in your browser; the site will still load.</p>

<h2>7. Legal bases (GDPR)</h2>
<ul>
<li><strong>Legitimate interests:</strong> running the site, security, understanding aggregate traffic, publishing our own catalogues, clearing copyright claims you ask us to clear.</li>
<li><strong>Consent:</strong> newsletter (when the form is live); non-essential analytics where required by your jurisdiction.</li>
<li><strong>Contract:</strong> performing a licence or studio booking you request.</li>
<li><strong>Legal obligation:</strong> tax, accounting, or lawful requests.</li>
</ul>

<h2>8. Retention</h2>
<p>Analytics is retained per our GA4 settings. Emails and claim evidence are kept as long as needed to handle the request and defend rights, then deleted or archived. Newsletter addresses until you unsubscribe or we shut the list. YouTube/Meta tokens until we revoke them or stop the publisher. Cloudflare logs per provider defaults.</p>

<h2>9. Recipients and transfers</h2>
<p>Processors and independent controllers may include Cloudflare (hosting/CDN), Google (Analytics, YouTube API, Cloud Console), Beatstars, Pond5, Spotify/Apple (public catalogue lookups at build time), Discord, Meta, and email providers. Some are outside the EEA; transfers rely on the provider’s GDPR mechanisms (e.g. SCCs) where applicable.</p>

<h2>10. Your rights</h2>
<p>If GDPR applies, you may request access, rectification, erasure, restriction, portability, and objection, and you may withdraw consent. Email <a href="mailto:mrbonzomusic@gmail.com">mrbonzomusic@gmail.com</a>. You may complain to the Hellenic Data Protection Authority (www.dpa.gr) or your local supervisory authority.</p>

<h2>11. Children</h2>
<p>The site is aimed at artists and general audiences. We do not knowingly collect personal data from children under 16. Licensable music use must follow Beatstars’ age and contract rules.</p>

<h2>12. Security</h2>
<p>TLS on the public site, secrets kept out of the client, newsletter keys only in server environment variables, OAuth secrets only on the publisher host. No method is perfectly secure.</p>

<h2>13. Changes</h2>
<p>We will update this page and the “Last updated” date when practices change in a material way. Continued use of the site after an update means you have read the new text.</p>

<h2>14. Contact</h2>
<p>Privacy requests: <a href="mailto:mrbonzomusic@gmail.com">mrbonzomusic@gmail.com</a>. Related documents: <a href="/terms">Terms of Service</a>.</p>
`.trim();

export const termsHtml = `
<h2>1. Agreement</h2>
<p>These Terms of Service govern access to <a href="https://mrbonzo.com/">https://mrbonzo.com</a> (including <a href="https://mrbonzo-beats.pages.dev/">mrbonzo-beats.pages.dev</a>), content we publish as Mr. Bonzo, and related studio enquiries. Operator: <strong>Alexandros Pilatos</strong> (Mr. Bonzo / Purple Sound Studio), Athens, Greece. Contact: <a href="mailto:mrbonzomusic@gmail.com">mrbonzomusic@gmail.com</a>.</p>
<p>By using the site you agree to these Terms and to the <a href="/privacy">Privacy Policy</a>. If you do not agree, do not use the site. Beat, kit, and licence purchases are also governed by the store’s contract (usually Beatstars) at checkout — those terms control the licence grant.</p>

<h2>2. Who we are and what we offer</h2>
<p>We are a music producer and audio engineer. Through this site and linked stores we offer type beats and sound kits; streaming releases; media for artists and audiovisual work; and services such as production, recording, mixing, mastering, sound design, and scoring. Listings, prices, and licence tiers on the site (for example Basic Lease, Premium Lease, Exclusive) are summaries. The binding licence is the one you accept on Beatstars or another store, or a written agreement we sign with you.</p>

<h2>3. Intellectual property</h2>
<p>Unless a licence you purchased says otherwise, we (or our licensors) own the music, mixes, kits, artwork, logos, photographs, text, and software on this site. You may browse and share links to public pages. You may not copy, resell, upload our unlicensed instrumentals to Content ID as your own, train generative models on our catalogue, or remove credits, except as a valid licence expressly allows.</p>
<p>Artist names in the collaborations list are used to describe past work. They do not imply current endorsement unless stated.</p>

<h2>4. Beats, kits, and licences</h2>
<ul>
<li><strong>Paid licences:</strong> granted by Beatstars (or Pond5 / a written deal). Usage limits (file type, copies, streams, exclusive vs non-exclusive) are those of the product you bought. Exclusive licences typically require the beat to be taken down from non-exclusive sale after clearance.</li>
<li><strong>Free section:</strong> beats we mark as free may be used commercially as described on the listing, still subject to credit where requested and to our right to stop abuse. Free does not mean you own the copyright or can register the instrumental as solely yours on Content ID in a way that blocks us or other legitimate licensees.</li>
<li><strong>Claims:</strong> if YouTube or another platform claims a track, contact us with the video URL. For a paid beat, include a receipt screenshot. We whitelist legitimate uses as soon as reasonably possible (we aim for 24 hours on business days). We cannot control every third-party Content ID database.</li>
<li><strong>Refunds:</strong> digital licences follow the store’s refund policy. Custom studio work follows the quote we send you.</li>
</ul>

<h2>5. Studio services</h2>
<p>Quotes, files, and revisions for production, mix, master, or scoring are agreed in writing (email is enough). Deadlines depend on materials you deliver. We may refuse work that is unlawful or that we cannot clear. You warrant that you have rights in vocals, samples, and names you ask us to use.</p>

<h2>6. Third-party services</h2>
<p>Players, checkout, Discord, social networks, Spotify, Apple Music, YouTube, Google Analytics, and Cloudflare are independent services. Their terms apply when you use them. We are not liable for outages or policy actions of those platforms.</p>

<h2>7. YouTube API, Google Cloud, and automated publishing</h2>
<p>We use Google Cloud OAuth and YouTube API Services in a private application that uploads, schedules, updates, organises, and removes videos on YouTube channels we own (@mrbonzobeats, @mrbonzomusic), and may similarly publish to other channels we operate. That application is for our studio operations, not a public login on this website.</p>
<p>Use of YouTube API Services is subject to the <a href="https://www.youtube.com/t/terms" rel="noopener noreferrer" target="_blank">YouTube Terms of Service</a> and <a href="https://developers.google.com/youtube/terms/api-services-terms-of-service" rel="noopener noreferrer" target="_blank">YouTube API Services Terms</a>. Google’s data practices are described in the <a href="https://policies.google.com/privacy" rel="noopener noreferrer" target="_blank">Google Privacy Policy</a>. Our handling of API data is described in the <a href="/privacy">Privacy Policy</a> (section “YouTube API Services”). Channel owners can revoke access at <a href="https://myaccount.google.com/permissions" rel="noopener noreferrer" target="_blank">Google Account permissions</a>.</p>
<p>Videos the publisher posts remain our content (or content we are authorised to post). Automated posting does not transfer copyright to n8n, Google, or site visitors.</p>

<h2>8. Acceptable use</h2>
<p>You must not attack the site, scrape in a way that harms the service, impersonate us, or use contact forms/email for spam. We may block IPs or accounts that abuse the site or our stores.</p>

<h2>9. Disclaimers</h2>
<p>The site is provided “as is”. Previews, stems availability, and third-party players may fail. We do not warrant that a beat will be unique forever, that a mix will chart, or that a platform will never claim a licensed video. Information on the site may lag behind the store.</p>

<h2>10. Liability</h2>
<p>To the maximum extent allowed by Greek and EU consumer law, we are not liable for indirect, incidental, or consequential loss (lost streams, demonetisation, lost data) arising from the site or from automated publishing delays. For paid licences, our liability is limited to the amount you paid for that licence, except in cases of intent, gross negligence, or injury where liability cannot be limited. Mandatory consumer rights remain unaffected.</p>

<h2>11. Indemnity</h2>
<p>If you use our music beyond your licence, or supply infringing vocals/samples for a custom job, you will defend and indemnify us against resulting claims, damages, and reasonable legal costs.</p>

<h2>12. Governing law</h2>
<p>These Terms are governed by the laws of Greece, without prejudice to mandatory consumer protections of your country of residence in the EU/EEA. Courts of Athens, Greece, have jurisdiction, except where the law gives you the right to sue in your home courts.</p>

<h2>13. Changes</h2>
<p>We may update these Terms. The date at the top is the effective date. Material changes will be posted on this page. The current version applies to use after it is published.</p>

<h2>14. Contact</h2>
<p><a href="mailto:mrbonzomusic@gmail.com">mrbonzomusic@gmail.com</a> · <a href="/privacy">Privacy Policy</a> · <a href="https://mrbonzo.com/">mrbonzo.com</a></p>
`.trim();
