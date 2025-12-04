import { cn } from '@/lib/utils';

interface AgentOption {
  id: string;
  name: string;
  description: string;
  icon: string;
  badge?: string;
}

const AGENT_OPTIONS: AgentOption[] = [
  {
    id: 'interactive',
    name: 'Interactive Sales Agent',
    description:
      'Full conversation with lead qualification, objection handling, and RAG-powered responses',
    icon: '🤝',
    badge: 'Default',
  },
  {
    id: 'announcement',
    name: 'Activation Announcement',
    description: 'One-way congratulatory message for captain activation (no interaction)',
    icon: '🎉',
  },
];

interface AgentSelectorProps {
  selectedAgent: string;
  onAgentChange: (agentId: string) => void;
}

export const AgentSelector = ({ selectedAgent, onAgentChange }: AgentSelectorProps) => {
  return (
    <div className="mx-auto mt-8 w-full max-w-2xl">
      <div className="mb-4 text-center">
        <h3 className="text-fg0 mb-1 text-lg font-semibold">Choose Agent Type</h3>
        <p className="text-fg1 text-sm">Select which agent you want to test</p>
      </div>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        {AGENT_OPTIONS.map((agent) => (
          <button
            key={agent.id}
            onClick={() => onAgentChange(agent.id)}
            className={cn(
              'relative rounded-xl border-2 p-5 text-left transition-all duration-200',
              'hover:scale-[1.02] hover:shadow-lg',
              selectedAgent === agent.id
                ? 'border-blue-500 bg-blue-50 shadow-md dark:bg-blue-950/20'
                : 'border-gray-200 bg-white dark:border-gray-700 dark:bg-gray-800'
            )}
          >
            {agent.badge && (
              <span className="absolute top-2 right-2 rounded-full bg-blue-100 px-2 py-0.5 text-xs font-medium text-blue-700 dark:bg-blue-900 dark:text-blue-200">
                {agent.badge}
              </span>
            )}

            <div className="flex items-start gap-3">
              <div className="mt-1 text-3xl">{agent.icon}</div>
              <div className="flex-1">
                <h4 className="text-fg0 mb-1 pr-16 font-semibold">{agent.name}</h4>
                <p className="text-fg1 text-sm leading-relaxed">{agent.description}</p>
              </div>
            </div>

            {selectedAgent === agent.id && (
              <div className="absolute right-3 bottom-3">
                <svg
                  className="h-5 w-5 text-blue-500"
                  fill="currentColor"
                  viewBox="0 0 20 20"
                  xmlns="http://www.w3.org/2000/svg"
                >
                  <path
                    fillRule="evenodd"
                    d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z"
                    clipRule="evenodd"
                  />
                </svg>
              </div>
            )}
          </button>
        ))}
      </div>
    </div>
  );
};
