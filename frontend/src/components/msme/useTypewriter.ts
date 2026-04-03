import { useEffect, useState } from 'react';

export default function useTypewriter(text: string, speed = 18): string {
  const [displayed, setDisplayed] = useState('');

  useEffect(() => {
    setDisplayed('');

    if (!text) {
      return;
    }

    let index = 0;
    const interval = window.setInterval(() => {
      index += 1;
      setDisplayed(text.slice(0, index));

      if (index >= text.length) {
        window.clearInterval(interval);
      }
    }, speed);

    return () => window.clearInterval(interval);
  }, [speed, text]);

  return displayed;
}
