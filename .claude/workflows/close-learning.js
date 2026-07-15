export const meta = {
  name: 'close-learning',
  description: 'Valida las predicciones expiradas contra el mercado y cierra el loop de aprendizaje',
  phases: [
    { title: 'Descubrir', detail: 'precios actuales + predicciones cuyo timeframe venció', model: 'haiku' },
    { title: 'Evaluar', detail: 'un agente por predicción: verifica vs histórico y guarda la evaluación NL', model: 'sonnet' },
    { title: 'Sintetizar', detail: 'track record por setup + lecciones', model: 'opus' },
  ],
}

// ---------------------------------------------------------------------------
// Esquemas de salida estructurada (el runtime obliga al agente a devolverlos)
// ---------------------------------------------------------------------------
const EXPIRED_SCHEMA = {
  type: 'object',
  required: ['predictions'],
  properties: {
    predictions: {
      type: 'array',
      items: {
        type: 'object',
        required: ['id', 'symbol', 'prediction', 'timeframe_hours', 'created_at'],
        properties: {
          id: { type: 'string' },
          symbol: { type: 'string' },
          prediction: { type: 'string' },
          target_value: { type: ['number', 'null'] },
          timeframe_hours: { type: 'number' },
          created_at: { type: 'string' },
        },
      },
    },
  },
}

const VERDICT_SCHEMA = {
  type: 'object',
  required: ['id', 'outcome', 'evaluation'],
  properties: {
    id: { type: 'string' },
    outcome: { type: 'string', enum: ['correct', 'incorrect', 'partial'] },
    actual_value: { type: ['number', 'null'] },
    evaluation: { type: 'string' }, // el análisis en lenguaje natural que se guarda en la DB
  },
}

// ---------------------------------------------------------------------------
// Fase 1 — Descubrir qué predicciones ya vencieron
// ---------------------------------------------------------------------------
phase('Descubrir')
const discovery = await agent(
  `Eres el learning-agent del Crypto Trading Desk. Lee agents/learning-agent.md para tu marco de análisis.
   Tu tarea es LISTAR las predicciones cuyo timeframe ya venció y siguen en estado 'pending'.
   1. Usa get_crypto_prices() (crypto-data MCP) para obtener el precio actual de las monedas relevantes
      (bitcoin, ethereum, solana, avalanche-2, aptos, chainlink, uniswap, aave, pendle, worldcoin, jito...).
   2. Llama find_expired_predictions(current_prices='{"BTC/USDT": ..., "ETH/USDT": ..., ...}') de crypto-learning-db.
   Devuelve SOLO las predicciones expiradas y pendientes, con id, symbol, prediction, target_value, timeframe_hours y created_at.
   NO valides todavía. NO uses la herramienta Edit.`,
  { label: 'find-expired', phase: 'Descubrir', model: 'haiku', schema: EXPIRED_SCHEMA },
)

const preds = (discovery && discovery.predictions) || []
if (!preds.length) {
  log('No hay predicciones expiradas pendientes. El loop ya está al día.')
  return { evaluated: 0, verdicts: [], report: 'Sin predicciones expiradas por validar.' }
}
log(`${preds.length} predicciones expiradas para evaluar en paralelo`)

// ---------------------------------------------------------------------------
// Fase 2 — Evaluar cada predicción (un agente por predicción, en paralelo)
// ---------------------------------------------------------------------------
phase('Evaluar')
const verdicts = await pipeline(
  preds,
  (p) =>
    agent(
      `Eres el learning-agent. Evalúa UNA predicción y guarda el resultado.

       Predicción [${p.id}] · ${p.symbol}
       Enunciado: "${p.prediction}"
       Target: ${p.target_value ?? 'n/a'} · Ventana: ${p.timeframe_hours}h desde ${p.created_at}

       Pasos:
       1. Usa fetch_ohlcv_data(symbol='${p.symbol}', timeframe='1h' o '4h') de crypto-exchange para cubrir la ventana
          de la predicción (desde created_at hasta created_at + timeframe_hours). Mira máximos/mínimos alcanzados.
       2. Razona si la predicción se CUMPLIÓ, NO se cumplió, o fue PARCIAL, y qué tan cerca estuvo del target.
       3. Guarda el resultado llamando validate_prediction() de crypto-learning-db con:
          - prediction_id = '${p.id}'
          - un actual_outcome/valor real observado
          - evaluation = tu análisis en lenguaje natural (por qué acertó o falló, qué señal era fiable).
       Devuelve el veredicto estructurado. NO uses la herramienta Edit.`,
      { label: `eval:${p.id}`, phase: 'Evaluar', model: 'sonnet', schema: VERDICT_SCHEMA },
    ),
)

const done = verdicts.filter(Boolean)
const correct = done.filter((v) => v.outcome === 'correct').length
log(`${done.length}/${preds.length} evaluadas · ${correct} correctas`)

// ---------------------------------------------------------------------------
// Fase 3 — Sintetizar el track record y las lecciones
// ---------------------------------------------------------------------------
phase('Sintetizar')
const report = await agent(
  `Eres el learning-agent. Acabas de validar ${done.length} predicciones. Veredictos:
   ${JSON.stringify(done)}

   1. Llama get_prediction_track_record() de crypto-learning-db para ver la precisión por tipo de setup (7d/30d/90d/global).
   2. Opcional: llama generate_summary() si corresponde generar un resumen de periodo.
   Devuelve un reporte en MARKDOWN con:
   - Precisión total y por tipo de setup (price_target, support_hold, funding_squeeze, ...).
   - Qué setups son más fiables y cuáles no, con evidencia de las evaluaciones.
   - 2-3 lecciones accionables para las próximas entradas.
   NO uses la herramienta Edit.`,
  { label: 'synthesize', phase: 'Sintetizar', model: 'opus' },
)

return { evaluated: done.length, correct, verdicts: done, report }
