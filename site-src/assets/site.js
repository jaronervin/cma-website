// Mobile menu, hero carousel, and client-side search. No dependencies.

(function menu() {
  const toggle = document.querySelector(".menu-toggle");
  const nav = document.getElementById("site-nav");
  if (!toggle || !nav) return;
  toggle.addEventListener("click", () => {
    const open = nav.classList.toggle("is-open");
    toggle.setAttribute("aria-expanded", open);
  });
  nav.querySelectorAll(".sub-toggle").forEach((btn) => {
    btn.addEventListener("click", () => {
      const sub = btn.nextElementSibling;
      const open = sub.classList.toggle("is-open");
      btn.setAttribute("aria-expanded", open);
    });
  });
})();

(function carousel() {
  const hero = document.querySelector(".hero");
  if (!hero) return;
  const slides = [...hero.querySelectorAll(".slide")];
  let i = 0;
  const show = (n) => {
    slides[i].classList.remove("is-active");
    i = (n + slides.length) % slides.length;
    slides[i].classList.add("is-active");
  };
  hero.querySelector(".hero-prev").addEventListener("click", () => show(i - 1));
  hero.querySelector(".hero-next").addEventListener("click", () => show(i + 1));
  if (!matchMedia("(prefers-reduced-motion: reduce)").matches) {
    setInterval(() => show(i + 1), 6000);
  }
})();

(async function search() {
  const results = document.getElementById("results");
  if (!results) return;
  const q = new URLSearchParams(location.search).get("q") || "";
  document.getElementById("q").value = q;
  const terms = q.toLowerCase().split(/\s+/).filter(Boolean);
  if (!terms.length) return;
  const base = document.documentElement.dataset.base || "";
  const index = await (await fetch(base + "/search-index.json")).json();
  const scored = index
    .map((d) => {
      const title = d.t.toLowerCase(), text = d.x.toLowerCase();
      let score = 0;
      for (const t of terms) {
        if (title.includes(t)) score += 5;
        else if (text.includes(t)) score += 1;
        else return null;
      }
      return { d, score };
    })
    .filter(Boolean)
    .sort((a, b) => b.score - a.score || (b.d.d || "").localeCompare(a.d.d || ""));
  results.innerHTML = scored.length
    ? scored.slice(0, 40).map(({ d }) => {
        const li = document.createElement("li");
        const a = document.createElement("a");
        a.href = base + d.u; a.textContent = d.t;
        const small = document.createElement("small");
        small.textContent = (d.d ? d.d + " · " : "") + d.x.slice(0, 180) + "…";
        li.append(a, small);
        return li.outerHTML;
      }).join("")
    : "<li>No results.</li>";
})();
