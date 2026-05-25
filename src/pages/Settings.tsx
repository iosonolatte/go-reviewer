import React, { useState, useEffect } from 'react';
import { Save, Server, Brain, Info } from 'lucide-react';
import { useGameStore } from '../store/gameStore';

const Settings: React.FC = () => {
  const { katagoConfig, llmConfig, setKatagoConfig, setLLMConfig } = useGameStore();
  const [saveStatus, setSaveStatus] = useState<'idle' | 'saving' | 'success' | 'error'>('idle');

  const [katagoForm, setKatagoForm] = useState({
    path: katagoConfig.path,
    configPath: katagoConfig.configPath,
    modelPath: katagoConfig.modelPath,
    analyzeTime: katagoConfig.analyzeTime
  });

  const [llmForm, setLLMForm] = useState({
    apiKey: llmConfig.apiKey,
    model: llmConfig.model,
    baseUrl: llmConfig.baseUrl || ''
  });

  useEffect(() => {
    setKatagoForm({
      path: katagoConfig.path,
      configPath: katagoConfig.configPath,
      modelPath: katagoConfig.modelPath,
      analyzeTime: katagoConfig.analyzeTime
    });
    setLLMForm({
      apiKey: llmConfig.apiKey,
      model: llmConfig.model,
      baseUrl: llmConfig.baseUrl || ''
    });
  }, [katagoConfig, llmConfig]);

  const saveKatagoConfig = async () => {
    setSaveStatus('saving');
    try {
      const response = await fetch('http://localhost:5000/api/config/katago', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(katagoForm)
      });

      if (response.ok) {
        setKatagoConfig(katagoForm);
        setSaveStatus('success');
        setTimeout(() => setSaveStatus('idle'), 2000);
      } else {
        throw new Error('保存失败');
      }
    } catch (error) {
      console.error('保存失败:', error);
      setSaveStatus('error');
      setTimeout(() => setSaveStatus('idle'), 2000);
    }
  };

  const saveLLMConfig = async () => {
    setSaveStatus('saving');
    try {
      const response = await fetch('http://localhost:5000/api/config/llm', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          ...llmForm,
          baseUrl: llmForm.baseUrl || undefined
        })
      });

      if (response.ok) {
        setLLMConfig({
          apiKey: llmForm.apiKey,
          model: llmForm.model,
          baseUrl: llmForm.baseUrl || undefined
        });
        setSaveStatus('success');
        setTimeout(() => setSaveStatus('idle'), 2000);
      } else {
        throw new Error('保存失败');
      }
    } catch (error) {
      console.error('保存失败:', error);
      setSaveStatus('error');
      setTimeout(() => setSaveStatus('idle'), 2000);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-amber-50 via-orange-50 to-yellow-50 py-8">
      <div className="max-w-3xl mx-auto px-4">
        <h1 className="text-3xl font-serif font-bold text-go-wood mb-8 text-center">
          系统设置
        </h1>

        <div className="bg-white rounded-2xl shadow-xl p-6 mb-6">
          <div className="flex items-center gap-3 mb-6">
            <div className="w-10 h-10 rounded-lg bg-blue-100 flex items-center justify-center">
              <Server className="w-5 h-5 text-blue-600" />
            </div>
            <div>
              <h2 className="text-xl font-serif font-medium text-go-wood">
                KataGo 引擎配置
              </h2>
              <p className="text-sm text-go-woodLight">
                配置围棋引擎的路径和参数
              </p>
            </div>
          </div>

          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-go-wood mb-1">
                KataGo 可执行文件路径
              </label>
              <input
                type="text"
                value={katagoForm.path}
                onChange={(e) => setKatagoForm({ ...katagoForm, path: e.target.value })}
                placeholder="例如：/path/to/katago"
                className="w-full px-4 py-2 border border-go-board rounded-lg focus:ring-2 focus:ring-go-accent focus:border-transparent transition-all"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-go-wood mb-1">
                配置文件路径
              </label>
              <input
                type="text"
                value={katagoForm.configPath}
                onChange={(e) => setKatagoForm({ ...katagoForm, configPath: e.target.value })}
                placeholder="例如：/path/to/gtp_example.cfg"
                className="w-full px-4 py-2 border border-go-board rounded-lg focus:ring-2 focus:ring-go-accent focus:border-transparent transition-all"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-go-wood mb-1">
                模型权重文件路径
              </label>
              <input
                type="text"
                value={katagoForm.modelPath}
                onChange={(e) => setKatagoForm({ ...katagoForm, modelPath: e.target.value })}
                placeholder="例如：/path/to/model.bin.gz"
                className="w-full px-4 py-2 border border-go-board rounded-lg focus:ring-2 focus:ring-go-accent focus:border-transparent transition-all"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-go-wood mb-2">
                分析速度档位（visits 数量）
              </label>
              <div className="grid grid-cols-5 gap-2 mb-2">
                {[
                  { label: '⚡极速', value: 1, visits: 60, desc: '~1秒/手' },
                  { label: '🏃快速', value: 3, visits: 120, desc: '~2秒/手' },
                  { label: '⚖️均衡', value: 5, visits: 200, desc: '~3秒/手' },
                  { label: '🎯精确', value: 10, visits: 400, desc: '~6秒/手' },
                  { label: '🔬深度', value: 20, visits: 800, desc: '~12秒/手' }
                ].map((preset) => (
                  <button
                    key={preset.value}
                    type="button"
                    onClick={() => setKatagoForm({ ...katagoForm, analyzeTime: preset.value })}
                    className={`px-2 py-2 rounded-lg text-xs font-medium transition-all border ${
                      katagoForm.analyzeTime === preset.value
                        ? 'bg-gradient-to-r from-blue-500 to-blue-600 text-white border-blue-600 shadow'
                        : 'bg-white text-go-wood border-go-board hover:bg-blue-50'
                    }`}
                  >
                    <div>{preset.label}</div>
                    <div className="text-[10px] mt-0.5 opacity-80">{preset.visits}</div>
                  </button>
                ))}
              </div>
              <p className="text-xs text-go-woodLight">
                当前档位 {katagoForm.analyzeTime} → 每手约 {katagoForm.analyzeTime * 40} 次 visits。
                值越大越准但越慢。实时落子推荐 <b>极速</b> 或 <b>快速</b>，复盘推荐 <b>均衡</b>。
              </p>
            </div>

            <button
              onClick={saveKatagoConfig}
              disabled={saveStatus === 'saving'}
              className="w-full px-6 py-3 bg-gradient-to-r from-blue-500 to-blue-600 text-white rounded-lg hover:shadow-lg transition-all disabled:opacity-50 flex items-center justify-center gap-2 font-medium"
            >
              <Save className="w-5 h-5" />
              保存 KataGo 配置
            </button>
          </div>
        </div>

        <div className="bg-white rounded-2xl shadow-xl p-6 mb-6">
          <div className="flex items-center gap-3 mb-6">
            <div className="w-10 h-10 rounded-lg bg-purple-100 flex items-center justify-center">
              <Brain className="w-5 h-5 text-purple-600" />
            </div>
            <div>
              <h2 className="text-xl font-serif font-medium text-go-wood">
                大语言模型配置
              </h2>
              <p className="text-sm text-go-woodLight">
                配置 AI 解说使用的大语言模型
              </p>
            </div>
          </div>

          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-go-wood mb-1">
                API Key
              </label>
              <input
                type="password"
                value={llmForm.apiKey}
                onChange={(e) => setLLMForm({ ...llmForm, apiKey: e.target.value })}
                placeholder="sk-..."
                className="w-full px-4 py-2 border border-go-board rounded-lg focus:ring-2 focus:ring-go-accent focus:border-transparent transition-all"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-go-wood mb-1">
                模型名称
              </label>
              <input
                type="text"
                value={llmForm.model}
                onChange={(e) => setLLMForm({ ...llmForm, model: e.target.value })}
                placeholder="例如：gpt-4, gpt-3.5-turbo"
                className="w-full px-4 py-2 border border-go-board rounded-lg focus:ring-2 focus:ring-go-accent focus:border-transparent transition-all"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-go-wood mb-1">
                API Base URL（可选）
              </label>
              <input
                type="text"
                value={llmForm.baseUrl}
                onChange={(e) => setLLMForm({ ...llmForm, baseUrl: e.target.value })}
                placeholder="例如：https://api.openai.com/v1"
                className="w-full px-4 py-2 border border-go-board rounded-lg focus:ring-2 focus:ring-go-accent focus:border-transparent transition-all"
              />
            </div>

            <button
              onClick={saveLLMConfig}
              disabled={saveStatus === 'saving'}
              className="w-full px-6 py-3 bg-gradient-to-r from-purple-500 to-purple-600 text-white rounded-lg hover:shadow-lg transition-all disabled:opacity-50 flex items-center justify-center gap-2 font-medium"
            >
              <Save className="w-5 h-5" />
              保存 LLM 配置
            </button>
          </div>
        </div>

        <div className="bg-white rounded-2xl shadow-xl p-6">
          <div className="flex items-center gap-3 mb-4">
            <div className="w-10 h-10 rounded-lg bg-green-100 flex items-center justify-center">
              <Info className="w-5 h-5 text-green-600" />
            </div>
            <h2 className="text-xl font-serif font-medium text-go-wood">
              使用说明
            </h2>
          </div>

          <div className="space-y-3 text-go-woodLight text-sm">
            <p>
              <strong>1. 获取 KataGo：</strong> 从{' '}
              <a
                href="https://github.com/lightvector/KataGo/releases"
                target="_blank"
                rel="noopener noreferrer"
                className="text-go-accent hover:underline"
              >
                KataGo 官方 GitHub
              </a>{' '}
              下载最新版本的引擎和权重文件。
            </p>
            <p>
              <strong>2. 配置引擎：</strong> 填写 KataGo 可执行文件、配置文件（gtp_example.cfg）和权重文件（如 kata1-b18c384nbt.bin.gz）的路径。
            </p>
            <p>
              <strong>3. 配置大语言模型：</strong> 填写 OpenAI API Key 或其他兼容 OpenAI 协议的服务配置。
            </p>
            <p>
              <strong>4. 启动后端：</strong> 进入 backend 目录，运行 <code className="bg-go-board px-2 py-0.5 rounded">pip install -r requirements.txt</code> 安装依赖，然后运行 <code className="bg-go-board px-2 py-0.5 rounded">python app.py</code> 启动后端服务。
            </p>
            <p>
              <strong>5. 开始复盘：</strong> 上传 .sgf 格式的棋谱文件，即可开始智能复盘。
            </p>
          </div>
        </div>

        {(saveStatus === 'success' || saveStatus === 'error') && (
          <div
            className={`fixed bottom-8 right-8 px-6 py-3 rounded-lg shadow-lg text-white ${
              saveStatus === 'success' ? 'bg-green-500' : 'bg-red-500'
            }`}
          >
            {saveStatus === 'success' ? '保存成功！' : '保存失败，请重试'}
          </div>
        )}
      </div>
    </div>
  );
};

export default Settings;
