import { Logo } from "@/components/Logo";

/** Info column beside the desktop device frame — just the lockup.
 * Hidden below 900px (see the .shell-aside rules in globals.css). */
export function PresentationAside() {
  return (
    <aside className="shell-aside">
      <Logo size={24} />
    </aside>
  );
}
