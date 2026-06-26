// The signature element: the buddy speaks in chat bubbles.
export function BuddyMessage({
  children, conf, tone = "signal",
}: { children: React.ReactNode; conf?: string; tone?: "signal" | "gain" | "loss" }) {
  return (
    <div className={`bubble ${tone === "gain" ? "gain" : tone === "loss" ? "loss" : ""}`}>
      <div className="who">
        <span className="dot">🤖</span> Buddy
        {conf && <span className="conf">· {conf} conf</span>}
      </div>
      <div>{children}</div>
    </div>
  );
}
