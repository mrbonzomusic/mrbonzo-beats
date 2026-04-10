interface SpotifyAlbumsParams {
  clientId?: string;
  clientSecret?: string;
  artistId?: string;
  fallbackCover: string;
}

interface SpotifyRelease {
  title: string;
  year: string;
  cover: string;
  spotify: string;
}

interface SpotifyResult {
  status: "live" | "rss" | "scrape" | "error";
  releases: SpotifyRelease[];
}

export async function getArtistAlbums({
  clientId,
  clientSecret,
  artistId,
  fallbackCover,
}: SpotifyAlbumsParams): Promise<SpotifyResult> {
  try {
    if (!clientId || !clientSecret || !artistId) {
      throw new Error("Missing Spotify Credentials");
    }

    // 1. Λήψη Token
    const authResponse = await fetch("https://accounts.spotify.com/api/token", {
      method: "POST",
      headers: {
        "Content-Type": "application/x-www-form-urlencoded",
        Authorization: `Basic ${btoa(`${clientId}:${clientSecret}`)}`,
      },
      body: "grant_type=client_credentials",
    });

    if (!authResponse.ok) {
      const errorText = await authResponse.text();
      throw new Error(`Auth Failed: ${authResponse.status} - ${errorText}`);
    }

    const authData = await authResponse.json();
    const accessToken = authData.access_token;

    // 2. Λήψη Albums/Singles
    const artistResponse = await fetch(
      `https://api.spotify.com/v1/artists/${artistId}/albums?include_groups=album,single&limit=20&market=GR`,
      {
        headers: { Authorization: `Bearer ${accessToken}` },
      }
    );

    if (!artistResponse.ok) {
      const errorText = await artistResponse.text();
      throw new Error(`Artist Fetch Failed: ${artistResponse.status} - ${errorText}`);
    }

    const data = await artistResponse.json();
    const items = Array.isArray(data?.items) ? data.items : [];
    const seen = new Set();
    const releases: Array<SpotifyRelease & { releaseDate: string }> = [];

    for (const item of items) {
      const spotifyUrl = item?.external_urls?.spotify;
      if (!spotifyUrl || seen.has(spotifyUrl)) continue;
      seen.add(spotifyUrl);
      releases.push({
        title: item?.name || "Untitled",
        year: item?.release_date ? String(item.release_date).split("-")[0] : "",
        cover: item?.images?.[0]?.url || fallbackCover,
        spotify: spotifyUrl,
        releaseDate: item?.release_date || "",
      });
    }

    releases.sort((a, b) => String(b.releaseDate).localeCompare(String(a.releaseDate)));

    return {
      status: "live",
      releases: releases.slice(0, 6).map(({ releaseDate, ...release }) => release),
    };
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    console.error("--- SPOTIFY API CRITICAL ERROR ---");
    console.error(message);
    return {
      status: "error",
      releases: [],
    };
  }
}

export function extractSpotifyArtistId(spotifyUrl = "") {
  try {
    const match = String(spotifyUrl).match(/spotify\.com\/artist\/([a-zA-Z0-9]+)/);
    return match?.[1] || "";
  } catch {
    return "";
  }
}

export async function getReleasesFromSpotifyPage({
  artistUrl,
  fallbackCover,
}: {
  artistUrl?: string;
  fallbackCover: string;
}): Promise<SpotifyResult> {
  try {
    if (!artistUrl) {
      throw new Error("Missing Spotify artist URL");
    }

    const response = await fetch(artistUrl, {
      headers: {
        "User-Agent": "Mozilla/5.0",
      },
    });

    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(`Spotify page fetch failed: ${response.status} - ${errorText.slice(0, 180)}`);
    }

    const html = await response.text();
    const releases: SpotifyRelease[] = [];
    const seen = new Set<string>();
    const directMatches = [...html.matchAll(/href="\/album\/([A-Za-z0-9]+)"/g)];
    const escapedMatches = [...html.matchAll(/\\\/album\\\/([A-Za-z0-9]+)/g)];
    const albumIds = [
      ...directMatches.map((m) => ({ id: m[1], index: m.index ?? 0 })),
      ...escapedMatches.map((m) => ({ id: m[1], index: m.index ?? 0 })),
    ];

    for (const album of albumIds) {
      if (releases.length >= 8) break;
      const albumId = album.id;
      const spotify = `https://open.spotify.com/album/${albumId}`;
      if (seen.has(spotify)) continue;
      seen.add(spotify);

      // Take a short window after the album link to find title and image nearby.
      const start = album.index;
      const windowHtml = html.slice(start, start + 1800);
      const titleMatch =
        windowHtml.match(/aria-label="([^"]+)"/i) ||
        windowHtml.match(/alt="([^"]+)"/i) ||
        windowHtml.match(/title="([^"]+)"/i);
      const imageMatch =
        windowHtml.match(/src="(https:\/\/i\.scdn\.co\/image\/[^"]+)"/i) ||
        windowHtml.match(/src="([^"]+)"/i);
      const yearMatch = windowHtml.match(/\b(20\d{2}|19\d{2})\b/);

      releases.push({
        title: titleMatch ? stripHtml(titleMatch[1]) : "Untitled Release",
        year: yearMatch ? yearMatch[1] : "",
        cover: imageMatch ? decodeXml(imageMatch[1]) : fallbackCover,
        spotify,
      });
    }

    return {
      status: releases.length > 0 ? "scrape" : "error",
      releases: releases.slice(0, 6),
    };
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    console.error("--- SPOTIFY PAGE SCRAPER ERROR ---");
    console.error(message);
    return {
      status: "error",
      releases: [],
    };
  }
}

function decodeXml(value: string) {
  return value
    .replace(/<!\[CDATA\[(.*?)\]\]>/gs, "$1")
    .replace(/&amp;/g, "&")
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">");
}

function stripHtml(value: string) {
  return decodeXml(value).replace(/<[^>]+>/g, " ").replace(/\s+/g, " ").trim();
}

function extractTag(item: string, tagName: string) {
  const pattern = new RegExp(`<${tagName}[^>]*>([\\s\\S]*?)<\\/${tagName}>`, "i");
  const match = item.match(pattern);
  return match ? decodeXml(match[1]).trim() : "";
}

function extractAttr(item: string, tagName: string, attrName: string) {
  const pattern = new RegExp(`<${tagName}[^>]*${attrName}=["']([^"']+)["'][^>]*>`, "i");
  const match = item.match(pattern);
  return match ? decodeXml(match[1]).trim() : "";
}

export async function getReleasesFromRss({
  feedUrl,
  fallbackCover,
}: {
  feedUrl?: string;
  fallbackCover: string;
}): Promise<SpotifyResult> {
  try {
    if (!feedUrl) {
      throw new Error("Missing RELEASES_RSS_URL");
    }

    const response = await fetch(feedUrl, {
      headers: {
        "User-Agent": "MrBonzoBeats/1.0 (+https://mrbonzo-beats.pages.dev)",
        Accept: "application/rss+xml, application/xml, text/xml;q=0.9, */*;q=0.8",
      },
    });

    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(`RSS Fetch Failed: ${response.status} - ${errorText.slice(0, 160)}`);
    }

    const xml = await response.text();
    const itemMatches = [...xml.matchAll(/<item\b[\s\S]*?<\/item>/gi)].map((m) => m[0]);
    const seen = new Set<string>();
    const releases: Array<SpotifyRelease & { sortDate: number }> = [];

    for (const item of itemMatches) {
      const link = extractTag(item, "link");
      const title = stripHtml(extractTag(item, "title"));
      const pubDateRaw = extractTag(item, "pubDate");
      const description = extractTag(item, "description");
      const mediaCover = extractAttr(item, "media:content", "url") || extractAttr(item, "enclosure", "url");
      const htmlCoverMatch = description.match(/<img[^>]+src=["']([^"']+)["']/i);
      const cover = mediaCover || (htmlCoverMatch ? decodeXml(htmlCoverMatch[1]) : "") || fallbackCover;
      const parsedDate = pubDateRaw ? Date.parse(pubDateRaw) : NaN;
      const year = Number.isNaN(parsedDate) ? "" : String(new Date(parsedDate).getUTCFullYear());

      if (!link || !title || seen.has(link)) continue;
      seen.add(link);

      releases.push({
        title,
        year,
        cover,
        spotify: link,
        sortDate: Number.isNaN(parsedDate) ? 0 : parsedDate,
      });
    }

    releases.sort((a, b) => b.sortDate - a.sortDate);

    return {
      status: "rss",
      releases: releases.slice(0, 6).map(({ sortDate, ...release }) => release),
    };
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    console.error("--- RSS FEED ERROR ---");
    console.error(message);
    return {
      status: "error",
      releases: [],
    };
  }
}