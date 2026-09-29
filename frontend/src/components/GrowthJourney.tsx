import { Link } from 'react-router-dom';

type JourneyStep = 'assessment' | 'recommendations' | 'roadmap' | 'chat' | 'interview';

const steps: { key: JourneyStep; label: string; path: string }[] = [
  { key: 'assessment', label: '认识自己', path: '/assessment' },
  { key: 'recommendations', label: '选择方向', path: '/recommendations' },
  { key: 'roadmap', label: '制定路径', path: '/roadmap' },
  { key: 'chat', label: '顾问答疑', path: '/chat' },
  { key: 'interview', label: '面试验证', path: '/interview' }
];

export function GrowthJourney({ current }: { current?: JourneyStep }) {
  return (
    <nav className="growth-journey" aria-label="职业成长阶段">
      <span className="growth-journey-label">成长路径</span>
      <ol>
        {steps.map((step, index) => (
          <li key={step.key} className={step.key === current ? 'is-current' : ''}>
            <Link to={step.path} aria-current={step.key === current ? 'step' : undefined}>
              <span className="growth-journey-number">{String(index + 1).padStart(2, '0')}</span>
              <span>{step.label}</span>
            </Link>
          </li>
        ))}
      </ol>
    </nav>
  );
}
