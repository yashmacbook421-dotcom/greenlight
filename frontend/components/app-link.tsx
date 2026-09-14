"use client";

// Navigation adapter: the only place the views touch the router (Next.js App Router here).
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

export function AppLink({
  to,
  children,
  className,
  activeProps,
}: {
  to: string;
  children: ReactNode;
  className?: string;
  activeProps?: { className: string };
}) {
  const pathname = usePathname();
  const active = activeProps && (pathname === to || pathname.startsWith(`${to}/`));
  return (
    <Link href={to} className={cn(className, active && activeProps.className)}>
      {children}
    </Link>
  );
}

export function useAppNavigate() {
  const router = useRouter();
  return (to: string) => router.push(to);
}
