function Stars({ points }) {
  return (
    <g fill="#e2e8f0">
      {points.map(([x, y, r = 1.4], index) => (
        <circle key={`${x}-${y}-${index}`} cx={x} cy={y} r={r} opacity={0.75} />
      ))}
    </g>
  );
}

function Bird({ x, y, color = '#e2e8f0' }) {
  return (
    <path
      d={`M${x - 8} ${y} Q${x - 3} ${y - 6} ${x} ${y} Q${x + 3} ${y - 6} ${x + 8} ${y}`}
      fill="none"
      stroke={color}
      strokeWidth="2"
      strokeLinecap="round"
    />
  );
}

function Fish({ x, y, color = '#fbbf24', flip = false }) {
  return (
    <g transform={flip ? `translate(${x} ${y}) scale(-1 1)` : `translate(${x} ${y})`}>
      <ellipse cx="0" cy="0" rx="10" ry="5" fill={color} />
      <path d="M-9 0 L-15 -5 L-15 5 Z" fill={color} opacity="0.85" />
      <circle cx="5" cy="-1.5" r="1.2" fill="#0f172a" />
    </g>
  );
}

function Camel({ x, y }) {
  return (
    <g transform={`translate(${x} ${y})`} fill="#92400e">
      <path d="M-18 12 Q-16 -4 -4 -5 Q2 -14 8 -5 Q18 -3 20 12 L15 12 L13 3 L6 5 L2 15 L-2 15 L-4 5 L-11 4 L-13 15 L-18 15 Z" />
      <path d="M18 3 Q27 1 31 -7 Q33 -11 36 -9 Q37 -6 34 -3 Q28 7 20 10 Z" />
      <circle cx="33" cy="-8" r="1.2" fill="#fef3c7" />
    </g>
  );
}

export function TowersScene({ variant = 'a' }) {
  const b = variant === 'b';
  return (
    <>
      <rect width="400" height="300" fill="#101a3a" />
      <circle cx="333" cy="58" r="27" fill="#fbbf24" opacity="0.9" />
      <Stars points={[[40, 40], [88, 72], [145, 34], [205, 50], [270, 28], [360, 90], [380, 45], [60, 120]]} />
      <rect y="236" width="400" height="64" fill="#0e7490" />
      <rect y="230" width="400" height="9" rx="4" fill="#334155" />
      <path d="M0 258 Q35 250 70 258 T140 258 T210 258 T280 258 T350 258 T420 258" fill="none" stroke="#38bdf8" strokeWidth="2" opacity="0.35" />

      {/* البرج الرئيسي */}
      <rect x="190" y="96" width="38" height="140" rx="5" fill="#cbd5e1" />
      <ellipse cx="209" cy="112" rx="42" ry="30" fill="#38bdf8" />
      <ellipse cx="198" cy="104" rx="12" ry="7" fill="#bae6fd" opacity="0.55" />
      <path d="M188 90 L209 62 L230 90 Z" fill="#e2e8f0" />
      <path d="M203 62 L209 48 L215 62 Z" fill="#f87171" />
      {[0, 1, 2, 3].map((index) => {
        const cols = 2;
        const x = 198 + (index % cols) * 15;
        const y = 160 + Math.floor(index / cols) * 22;
        return (
          <rect
            key={index}
            x={x}
            y={y}
            width="8"
            height="11"
            rx="1.5"
            fill={index < 3 || b ? '#fde68a' : '#1e293b'}
            opacity={index < 3 || b ? 0.95 : 0.7}
          />
        );
      })}

      {/* برج صغير يمين */}
      <rect x="286" y="148" width="18" height="88" rx="4" fill="#cbd5e1" />
      <circle cx="295" cy="138" r="21" fill="#60a5fa" />
      <path d="M280 126 L295 110 L310 126 Z" fill="#e2e8f0" />

      {/* برج صغير يسار + العلم */}
      <rect x="106" y="158" width="18" height="78" rx="4" fill="#cbd5e1" />
      <circle cx="115" cy="147" r="21" fill="#22d3ee" />
      <path d="M100 135 L115 119 L130 135 Z" fill="#e2e8f0" />
      <line x1="145" y1="118" x2="145" y2="64" stroke="#e2e8f0" strokeWidth="3" />
      <path d="M145 68 L174 78 L145 88 Z" fill={b ? '#ef4444' : '#22c55e'} />

      {/* طيور: الصورة ب فيها طائر ثالث */}
      <Bird x={292} y={62} />
      <Bird x={322} y={82} />
      {b && <Bird x={345} y={55} />}

      {/* نخيل ثابت */}
      <g transform="translate(50 216)">
        <rect x="-3" y="0" width="6" height="28" fill="#78350f" />
        <path d="M0 0 Q-22 -8 -28 8 Q-10 2 0 4 Q16 -10 30 2 Q12 2 0 6 Q-4 20 -18 22 Q-8 10 0 6 Z" fill="#15803d" />
      </g>
    </>
  );
}

export function DhowScene({ variant = 'a' }) {
  const b = variant === 'b';
  return (
    <>
      <rect width="400" height="300" fill="#0c4a6e" />
      <Stars points={[[36, 54], [74, 30], [118, 72], [160, 40], [250, 38], [366, 106], [382, 52]]} />
      <circle cx={b ? 315 : 335} cy={b ? 58 : 72} r="24" fill="#fbbf24" opacity="0.95" />
      <g fill="#e2e8f0" opacity="0.72">
        <ellipse cx="88" cy="58" rx="26" ry="9" />
        <ellipse cx="108" cy="54" rx="17" ry="8" />
      </g>
      <rect y="178" width="400" height="122" fill="#0e7490" />
      <path d="M0 198 Q30 192 60 198 T120 198 T180 198 T240 198 T300 198 T360 198 T420 198" fill="none" stroke="#7dd3fc" strokeWidth="2" opacity="0.4" />
      <path d="M0 224 Q40 218 80 224 T160 224 T240 224 T320 224 T400 224" fill="none" stroke="#7dd3fc" strokeWidth="2" opacity="0.28" />

      <g>
        <line x1="205" y1="92" x2="205" y2="205" stroke="#78350f" strokeWidth="5" />
        <path d="M205 98 L205 188 L158 188 Z" fill={b ? '#ef4444' : '#f8fafc'} />
        <path d="M205 104 L205 188 L242 188 Z" fill={b ? '#fca5a5' : '#e2e8f0'} opacity="0.85" />
        <path d="M118 205 Q205 236 292 205 Q270 224 205 226 Q140 224 118 205 Z" fill="#7c2d12" />
        <path d="M120 207 Q205 230 290 207" fill="none" stroke="#fed7aa" strokeWidth="2" opacity="0.6" />
        <rect x="198" y="88" width="14" height="6" rx="2" fill="#78350f" />
      </g>

      <Fish x={268} y={244} />
      <Fish x={352} y={236} flip />
      {b && <Fish x={320} y={230} />}

      <g fill="#f8fafc" opacity="0.75">
        <path d="M30 268 Q34 264 38 268 Q42 264 46 268" fill="none" stroke="#f8fafc" strokeWidth="1.6" />
        <path d="M340 274 Q344 270 348 274 Q352 270 356 274" fill="none" stroke="#f8fafc" strokeWidth="1.6" />
      </g>
    </>
  );
}

export function DesertScene({ variant = 'a' }) {
  const b = variant === 'b';
  return (
    <>
      <rect width="400" height="300" fill="#2e1065" />
      <Stars points={[[38, 38], [96, 60], [142, 28], [196, 72], [256, 36], [300, 84], [378, 38], [356, 112]]} />
      <circle cx="340" cy="65" r="24" fill="#fef3c7" />
      {!b && <circle cx="351" cy="57" r="21" fill="#2e1065" />}
      <path d="M0 205 Q80 178 162 204 T330 200 T440 214 L400 300 L0 300 Z" fill="#b45309" />
      <path d="M0 245 Q95 222 200 250 T400 244 L400 300 L0 300 Z" fill="#92400e" />
      <Stars points={[[276, 128, 1], [312, 146, 1], [206, 110, 1]]} />

      <g>
        <path d="M218 250 L260 158 L302 250 Z" fill="#e7e5e4" />
        <path d="M218 250 L260 158 L302 250" fill="none" stroke="#a8a29e" strokeWidth="2" />
        <path d="M260 250 L260 210 L280 210 L280 250 Z" fill={b ? '#dc2626' : '#0f172a'} />
        <path d="M210 252 L260 144 L310 252" fill="none" stroke="#57534e" strokeWidth="2" opacity="0.55" />
        <line x1="260" y1="158" x2="260" y2="140" stroke="#78716c" strokeWidth="2" />
        <path d="M260 140 L282 146 L260 153 Z" fill="#f59e0b" />
      </g>

      <Camel x={140} y={205} />
      {b && <Camel x={180} y={207} />}

      <g>
        <rect x="328" y="218" width="8" height="28" fill="#78350f" />
        <path d="M332 214 Q312 208 306 220 Q320 218 332 222 Q344 206 358 214 Q344 218 332 224 Z" fill="#15803d" />
      </g>

      <ellipse cx="60" cy="272" rx="22" ry="5" fill="#78350f" opacity="0.45" />
      <ellipse cx="352" cy="286" rx="30" ry="6" fill="#78350f" opacity="0.4" />
    </>
  );
}

export function SouqScene({ variant = 'a' }) {
  const b = variant === 'b';
  return (
    <>
      <rect width="400" height="300" fill="#18181b" />
      <rect y="198" width="400" height="102" fill="#78350f" />
      <rect y="198" width="400" height="8" fill="#a16207" />
      <g fill="#27272a">
        <path d="M20 198 L20 96 Q55 48 90 96 L90 198 Z" />
        <path d="M300 198 L300 88 Q340 42 380 88 L380 198 Z" />
      </g>
      <g fill="#fbbf24" opacity="0.55">
        <rect x="46" y="112" width="10" height="16" rx="2" />
        <rect x="330" y="108" width="10" height="16" rx="2" />
      </g>

      {/* فوانيس: الصورة ب فيها فانوس ثالث */}
      <line x1="70" y1="0" x2="70" y2="60" stroke="#52525b" strokeWidth="1.5" />
      {[108, 152, ...(b ? [130] : [])].map((x, index) => (
        <g key={`${x}-${index}`} transform={`translate(${x} 94)`}>
          <line x1="0" y1="-34" x2="0" y2="-18" stroke="#71717a" strokeWidth="1.4" />
          <rect x="-9" y="-18" width="18" height="26" rx="4" fill="#f59e0b" opacity="0.9" />
          <rect x="-9" y="-18" width="18" height="26" rx="4" fill="none" stroke="#fde68a" strokeWidth="1" />
          <rect x="-4" y="-22" width="8" height="4" rx="1" fill="#a16207" />
          <rect x="-4" y="8" width="8" height="4" rx="1" fill="#a16207" />
        </g>
      ))}

      {/* مظلة متجر */}
      <g>
        <rect x="238" y="124" width="78" height="6" rx="2" fill="#a16207" />
        <path d="M236 122 L318 122 L306 88 L248 88 Z" fill={b ? '#f59e0b' : '#14b8a6'} />
        {[0, 1, 2, 3].map((index) => (
          <path
            key={index}
            d={`M${248 + index * 16} 88 L${242 + index * 16} 122 L${250 + index * 16} 122 L${256 + index * 16} 88 Z`}
            fill="#f8fafc"
            opacity="0.72"
          />
        ))}
      </g>

      {/* بضائع ثابتة */}
      <g>
        <rect x="44" y="218" width="92" height="10" rx="3" fill="#57534e" />
        <rect x="52" y="228" width="76" height="34" rx="3" fill="#292524" />
        <circle cx="70" cy="211" r="7" fill="#b45309" />
        <circle cx="90" cy="211" r="7" fill="#dc2626" />
        <circle cx="110" cy="211" r="7" fill="#ca8a04" />
      </g>

      {/* صندوق: الصورة ب أكبر */}
      {b ? (
        <g>
          <rect x="308" y="218" width="48" height="40" rx="3" fill="#a16207" />
          <rect x="308" y="218" width="48" height="40" rx="3" fill="none" stroke="#fde68a" strokeWidth="2" />
          <line x1="308" y1="238" x2="356" y2="238" stroke="#854d0e" strokeWidth="2" />
          <line x1="332" y1="218" x2="332" y2="258" stroke="#854d0e" strokeWidth="2" />
        </g>
      ) : (
        <g>
          <rect x="316" y="232" width="28" height="24" rx="3" fill="#a16207" />
          <rect x="316" y="232" width="28" height="24" rx="3" fill="none" stroke="#fde68a" strokeWidth="1.6" />
          <line x1="316" y1="244" x2="344" y2="244" stroke="#854d0e" strokeWidth="1.6" />
        </g>
      )}

      {/* معلّقات ثابتة */}
      <g stroke="#52525b" strokeWidth="1.5">
        <line x1="180" y1="0" x2="180" y2="40" />
        <line x1="214" y1="0" x2="214" y2="52" />
      </g>
      <rect x="172" y="40" width="16" height="22" rx="2" fill="#3f3f46" />
      <rect x="206" y="52" width="16" height="20" rx="2" fill="#3f3f46" />
    </>
  );
}

export function StadiumScene({ variant = 'a' }) {
  const b = variant === 'b';
  return (
    <>
      <rect width="400" height="300" fill="#0f172a" />
      <rect y="40" width="400" height="104" fill="#1e293b" />
      <g fill="#475569">
        {Array.from({ length: 24 }).map((_, index) => (
          <circle key={index} cx={16 + index * 16} cy={60 + (index % 3) * 18} r="4" />
        ))}
      </g>
      <rect y="144" width="400" height="156" fill="#166534" />
      <rect y="144" width="400" height="6" fill="#22c55e" />
      <path d="M60 300 Q200 190 340 300" fill="none" stroke="#86efac" strokeWidth="2" opacity="0.45" />

      {/* لوحة النتيجة */}
      <g>
        <rect x="152" y="54" width="96" height="52" rx="6" fill="#020617" stroke="#64748b" strokeWidth="2" />
        <text
          x="200"
          y="89"
          textAnchor="middle"
          fontSize="24"
          fontWeight="800"
          fill="#fbbf24"
          fontFamily="monospace"
        >
          {b ? '2 - 1' : '1 - 0'}
        </text>
        <rect x="166" y="42" width="68" height="8" rx="3" fill="#334155" />
      </g>

      {/* راية الركن */}
      <g>
        <line x1="330" y1="118" x2="330" y2="222" stroke="#f8fafc" strokeWidth="3" />
        <path d="M330 120 L366 132 L330 148 Z" fill={b ? '#facc15' : '#f8fafc'} />
      </g>

      {/* لاعبون ثابتون */}
      <g>
        <circle cx="170" cy="225" r="8" fill="#f8fafc" />
        <rect x="166" y="232" width="8" height="18" rx="3" fill="#f8fafc" />
        <circle cx="250" cy="205" r="8" fill="#f87171" />
        <rect x="246" y="212" width="8" height="18" rx="3" fill="#f87171" />
        <circle cx="300" cy="252" r="7" fill="#f8fafc" />
        <rect x="296" y="258" width="8" height="16" rx="3" fill="#f8fafc" />
        <circle cx="200" cy="255" r="6" fill="#fbbf24" />
      </g>

      {/* أوشحة على السور */}
      <g>
        <rect x="82" y="216" width="30" height="9" rx="3" fill="#f87171" />
        <rect x="118" y="216" width="30" height="9" rx="3" fill="#f8fafc" />
        {b && <rect x="154" y="216" width="30" height="9" rx="3" fill="#fbbf24" />}
        <rect x="78" y="226" width="112" height="4" rx="2" fill="#64748b" />
      </g>
    </>
  );
}

export function MosqueScene({ variant = 'a' }) {
  const b = variant === 'b';
  return (
    <>
      <rect width="400" height="300" fill="#0b1220" />
      <Stars points={[[32, 44], [78, 24], [126, 62], [182, 32], [226, 76], [292, 40], [366, 92], [384, 34], [58, 112], [352, 150]]} />
      <circle cx="330" cy="65" r="22" fill="#fef3c7" />
      {!b && <circle cx="340" cy="57" r="19" fill="#0b1220" />}
      <rect y="252" width="400" height="48" fill="#111827" />
      <path d="M0 252 Q100 240 200 252 T400 250 L400 300 L0 300 Z" fill="#1f2937" />

      {/* المسجد */}
      <g>
        <rect x="158" y="190" width="162" height="64" fill="#e2e8f0" />
        <rect x="188" y="168" width="102" height="30" rx="4" fill="#f1f5f9" />
        <path d="M188 168 Q239 118 290 168 Z" fill="#f8fafc" />
        <path d="M236 128 Q239 118 242 128" fill="none" stroke="#fbbf24" strokeWidth="3" />
        <rect x="188" y="220" width="22" height="34" rx="10" fill="#0f172a" />
        <rect x="290" y="220" width="22" height="34" rx="10" fill="#0f172a" />
        <rect x="222" y="220" width="18" height="34" rx="2" fill="#0f172a" />
        <rect x="260" y="220" width="18" height="34" rx="2" fill="#0f172a" />

        {/* المئذنة */}
        <rect x="242" y="104" width="18" height="104" fill="#f1f5f9" />
        <rect x="238" y="120" width="26" height="7" rx="2" fill="#cbd5e1" />
        <rect x="239" y="102" width="24" height="8" rx="3" fill="#fbbf24" />
        <path d="M240 102 Q251 86 262 102 Z" fill="#f8fafc" />
        {b ? (
          <>
            <rect x="246" y="154" width="9" height="13" rx="2" fill="#f59e0b" />
            <rect x="246" y="178" width="9" height="13" rx="2" fill="#f59e0b" />
          </>
        ) : (
          <rect x="246" y="164" width="9" height="13" rx="2" fill="#f59e0b" />
        )}
      </g>

      {/* النخلة: تختفي في الصورة ب */}
      {!b && (
        <g transform="translate(90 190)">
          <rect x="-4" y="0" width="8" height="80" fill="#78350f" />
          <path d="M0 6 Q-28 -14 -38 8 Q-18 0 0 10 Q18 -16 38 2 Q18 2 0 12 Q-4 30 -24 34 Q-10 18 0 12 Z" fill="#15803d" />
        </g>
      )}

      <g fill="#1f2937">
        <rect x="40" y="228" width="46" height="30" rx="3" />
        <rect x="350" y="224" width="38" height="34" rx="3" />
      </g>
      <rect y="280" width="400" height="20" fill="#0f172a" opacity="0.65" />
    </>
  );
}

export const SPOT_SCENES = Object.freeze({
  towers: { title: 'أبراج الكويت', Component: TowersScene },
  dhow: { title: 'مركب في الخليج', Component: DhowScene },
  desert: { title: 'مخيّم بالبر', Component: DesertScene },
  souq: { title: 'سوق قديم', Component: SouqScene },
  stadium: { title: 'ملعب كورة', Component: StadiumScene },
  mosque: { title: 'مسجد بالليل', Component: MosqueScene },
});
