"use client"

import { useEffect, useId, useRef } from "react"

declare global {
  interface Window {
    TradingView?: any
    __tvScriptLoadingPromise?: Promise<void>
  }
}

type TradingChartProps = {
  symbol: string
  interval?: string
  theme?: "dark" | "light"
  studies?: string[]
  autosize?: boolean
}

export function TradingChart({
  symbol,
  interval = "60",
  theme = "dark",
  studies = ["MASimple@tv-basicstudies"],
  autosize = true,
}: TradingChartProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const widgetId = useId().replace(/:/g, "_")

  useEffect(() => {
    if (!containerRef.current || typeof window === "undefined") return

    let widget: any = null
    const config = {
      symbol,
      interval,
      timezone: "Etc/UTC",
      theme,
      style: "1",
      locale: "en",
      toolbar_bg: "#0b0f1c",
      hide_side_toolbar: false,
      allow_symbol_change: true,
      save_image: false,
      studies,
      autosize,
      withdateranges: true,
      hide_top_toolbar: false,
    }

    function createWidget() {
      if (containerRef.current && window.TradingView?.widget) {
        widget = new window.TradingView.widget({
          ...config,
          container_id: widgetId,
        })
      }
    }

    if (window.TradingView && window.TradingView.widget) {
      createWidget()
    } else {
      if (!window.__tvScriptLoadingPromise) {
        window.__tvScriptLoadingPromise = new Promise<void>((resolve) => {
          const script = document.createElement("script")
          script.id = "tradingview-widget-script"
          script.src = "https://s3.tradingview.com/tv.js"
          script.type = "text/javascript"
          script.onload = () => resolve()
          document.head.appendChild(script)
        })
      }
      window.__tvScriptLoadingPromise.then(createWidget)
    }

    return () => {
      widget?.remove?.()
    }
  }, [symbol, interval, theme, studies, autosize])

  return (
    <div className="w-full h-[420px] border border-border/40 rounded-lg overflow-hidden bg-card">
      <div id={widgetId} ref={containerRef} className="w-full h-full" />
    </div>
  )
}
