/** Share-intent links for social networks. */

export function shareTargets(url, text) {
  const u = encodeURIComponent(url);
  const tx = encodeURIComponent(text);
  return [
    { id: "x", label: "X", href: `https://x.com/intent/post?text=${tx}&url=${u}` },
    { id: "reddit", label: "Reddit", href: `https://www.reddit.com/submit?url=${u}&title=${tx}` },
    { id: "telegram", label: "Telegram", href: `https://t.me/share/url?url=${u}&text=${tx}` },
    { id: "whatsapp", label: "WhatsApp", href: `https://wa.me/?text=${encodeURIComponent(`${text} ${url}`)}` },
  ];
}
