import * as React from "react"
import { cn } from "@/lib/utils"

export interface BadgeProps extends React.HTMLAttributes<HTMLDivElement> {
  variant?: "default" | "secondary" | "destructive" | "outline" | "success" | "warning"
}

const badgeVariants = ({
  variant = "default",
  className,
}: {
  variant?: BadgeProps["variant"]
  className?: string
} = {}) => {
  const variants = {
    default: "border-transparent bg-primary text-primary-foreground shadow hover:bg-primary/80",
    secondary: "border-transparent bg-secondary text-secondary-foreground hover:bg-secondary/80",
    destructive: "border-transparent bg-destructive text-destructive-foreground shadow hover:bg-destructive/80",
    outline: "text-foreground border-border",
    success: "border-emerald-200 bg-emerald-50 text-emerald-700 font-medium",
    warning: "border-amber-200 bg-amber-50 text-amber-700 font-medium",
  }

  return cn(
    "inline-flex items-center rounded-md border px-2.5 py-0.5 text-xs font-semibold transition-colors focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2",
    variants[variant || "default"],
    className
  )
}

function Badge({ className, variant = "default", ...props }: BadgeProps) {
  return (
    <div className={badgeVariants({ variant, className })} {...props} />
  )
}

export { Badge, badgeVariants }
