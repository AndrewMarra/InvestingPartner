import Link from "next/link";
import { ensureProfile } from "@/app/actions";
import { SignOutButton } from "@/components/SignOutButton";

export default async function DashboardLayout({ children }: { children: React.ReactNode }) {
  await ensureProfile();
  return (
    <div className="shell">
      <nav className="nav">
        <Link href="/dashboard" className="brand">trading<b>buddy</b></Link>
        <div className="navlinks">
          <Link href="/dashboard">Overview</Link>
          <Link href="/dashboard/settings">Trade styles</Link>
          <Link href="/dashboard/keys">Keys &amp; alerts</Link>
          <SignOutButton />
        </div>
      </nav>
      {children}
    </div>
  );
}
