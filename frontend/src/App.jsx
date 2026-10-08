import { useCallback, useState } from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'

import { SimulatorShell } from './components/simulator/SimulatorShell'
import { TopBar } from './components/TopBar'
import { Dashboard } from './routes/Dashboard'
import { Estatisticas } from './routes/Estatisticas'
import { Historico } from './routes/Historico'

export default function App() {
  const [conexao, setConexao] = useState({ erro: null, carregando: true })
  const aoMudarConexao = useCallback((estado) => setConexao(estado), [])

  return (
    <div className="flex h-full flex-col">
      <TopBar erro={conexao.erro} carregando={conexao.carregando} />
      <Routes>
        <Route path="/" element={<Dashboard aoMudarConexao={aoMudarConexao} />} />
        <Route path="/estatisticas" element={<Estatisticas aoMudarConexao={aoMudarConexao} />} />
        <Route path="/historico" element={<Historico aoMudarConexao={aoMudarConexao} />} />
        <Route
          path="/sim/app"
          element={<SimulatorShell variante="app" aoMudarConexao={aoMudarConexao} />}
        />
        <Route
          path="/sim/whatsapp"
          element={<SimulatorShell variante="whatsapp" aoMudarConexao={aoMudarConexao} />}
        />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </div>
  )
}
