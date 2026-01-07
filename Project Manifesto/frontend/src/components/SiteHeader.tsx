import Link from "next/link";

export function SiteHeader() {
  return (
    <header className="site-header">
      <div className="site-header__inner">
        <Link href="/" className="brand">
          <span className="brand__accent">Quark</span>
          <span className="brand__rest">Media</span>
        </Link>
        <nav className="site-nav">
          <Link href="/" className="site-nav__link">
            Poster Wall
          </Link>
          <Link href="/movie/872585" className="site-nav__link">
            Sample Detail
          </Link>
        </nav>
      </div>
    </header>
  );
}