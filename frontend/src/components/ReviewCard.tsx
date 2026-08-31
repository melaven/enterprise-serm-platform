import { CheckCircle2, Star } from 'lucide-react'

type ReviewCardProps = {
  name: string
  role: string
  text: string
  rating?: number
}

export function ReviewCard({
  name,
  role,
  text,
  rating = 5,
}: ReviewCardProps) {
  return (
    <article className="rounded-2xl border border-slate-800 bg-slate-900/80 p-5 shadow-[0_16px_35px_rgba(15,23,42,0.35)] backdrop-blur-md transition-all duration-200 hover:-translate-y-0.5 hover:border-blue-500/60 hover:shadow-[0_20px_45px_rgba(59,130,246,0.18)]">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-base font-semibold text-slate-100">{name}</p>
          <p className="mt-1 text-sm text-slate-400">{role}</p>
        </div>

        <div className="inline-flex items-center gap-1 rounded-full bg-blue-500/10 px-2 py-1 text-blue-300 ring-1 ring-blue-500/20">
          <Star className="h-4 w-4 fill-current" />
          <span className="text-sm font-medium">{rating}</span>
        </div>
      </div>

      <div className="mt-4 flex items-center gap-2 text-sm font-medium text-emerald-300">
        <CheckCircle2 className="h-4 w-4" />
        <span>Verified review</span>
      </div>

      <p className="mt-3 text-sm leading-6 text-slate-300">{text}</p>
    </article>
  )
}
