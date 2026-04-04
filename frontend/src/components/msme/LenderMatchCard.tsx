import React, { useEffect, useState } from 'react';
import {
  AlertTriangle,
  Briefcase,
  Building,
  Building2,
  Factory,
  HandCoins,
  Landmark,
  Tag,
  Users,
} from 'lucide-react';
import styles from './LenderMatchCard.module.css';

export type LenderType =
  | 'public_bank'
  | 'private_bank'
  | 'nbfc'
  | 'mfi'
  | 'sidbi'
  | 'mudra'
  | 'nbfc_mfi'

export interface AlternativeLender {
  type: LenderType
  name: string
  note: string
  eligibility: 'high' | 'medium' | 'low'
}

export interface LenderMatch {
  primaryType: LenderType
  primaryName: string
  primaryReason: string
  schemeOrProduct: string
  schemeNote: string
  alternatives: AlternativeLender[]
  matchStrength: 'strong' | 'moderate' | 'marginal'
  fraudCaution: boolean
}

export interface LenderMatchCardProps {
  match: LenderMatch | null
  isLoading: boolean
}

function getLenderIcon(type: LenderType) {
  const map: Record<LenderType, React.ComponentType<{ size?: number; color?: string; className?: string }>> = {
    public_bank: Building2,
    private_bank: Building,
    nbfc: Briefcase,
    mfi: Users,
    sidbi: Factory,
    mudra: Landmark,
    nbfc_mfi: HandCoins,
  };
  return map[type] ?? Building2;
}

function getStrengthClass(
  strength: LenderMatch['matchStrength'],
  moduleStyles: Record<string, string>,
): string {
  return {
    strong: moduleStyles.strengthStrong,
    moderate: moduleStyles.strengthModerate,
    marginal: moduleStyles.strengthMarginal,
  }[strength];
}

function getStrengthLabel(strength: LenderMatch['matchStrength']): string {
  return {
    strong: 'Strong Match',
    moderate: 'Moderate Match',
    marginal: 'Marginal Match',
  }[strength];
}

function getEligClass(
  elig: AlternativeLender['eligibility'],
  moduleStyles: Record<string, string>,
): string {
  return {
    high: moduleStyles.eligHigh,
    medium: moduleStyles.eligMedium,
    low: moduleStyles.eligLow,
  }[elig];
}

function getEligLabel(elig: AlternativeLender['eligibility']): string {
  return { high: 'Good fit', medium: 'Possible', low: 'Later' }[elig];
}

function SkeletonAltRow() {
  return (
    <div className={styles.skeletonAltRow}>
      <div className={`${styles.skeletonCircle} ${styles.skeletonShimmer}`} style={{ width: 16, height: 16 }} />
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 6 }}>
        <div className={`${styles.skeletonBar} ${styles.skeletonShimmer}`} style={{ width: 140, height: 14 }} />
        <div className={`${styles.skeletonBar} ${styles.skeletonShimmer}`} style={{ width: 200, height: 11 }} />
      </div>
      <div className={`${styles.skeletonPill} ${styles.skeletonShimmer}`} style={{ width: 60, height: 20 }} />
    </div>
  );
}

export default function LenderMatchCard({
  match,
  isLoading,
}: LenderMatchCardProps) {
  const [isEntered, setIsEntered] = useState(false);

  useEffect(() => {
    if (!isLoading && match) {
      setIsEntered(false);
      const frame = window.requestAnimationFrame(() => setIsEntered(true));
      return () => window.cancelAnimationFrame(frame);
    }

    setIsEntered(false);
    return undefined;
  }, [isLoading, match]);

  if (isLoading) {
    return (
      <section className={`${styles.root} ${styles.cardPadding} ${styles.bodyFont}`}>
        <div className={styles.skeletonHeader}>
          <div className={styles.skeletonHeaderLeft}>
            <div className={`${styles.skeletonBar} ${styles.skeletonShimmer}`} style={{ width: 160, height: 18 }} />
            <div className={`${styles.skeletonBar} ${styles.skeletonShimmer}`} style={{ width: 200, height: 12 }} />
          </div>
          <div className={`${styles.skeletonPill} ${styles.skeletonShimmer}`} style={{ width: 100, height: 26 }} />
        </div>

        <div className={`${styles.rule} ${styles.mt4}`} />

        <div className={`${styles.skeletonPrimaryBlock} ${styles.skeletonShimmer} ${styles.mt5}`} />

        <div className={styles.mt6}>
          <div className={`${styles.skeletonBar} ${styles.skeletonShimmer}`} style={{ width: 140, height: 10 }} />
          <div className={styles.mt4}>
            <SkeletonAltRow />
            <SkeletonAltRow />
            <SkeletonAltRow />
          </div>
        </div>
      </section>
    );
  }

  if (!match) {
    return null;
  }

  const PrimaryIcon = getLenderIcon(match.primaryType);

  return (
    <section className={`${styles.root} ${styles.cardPadding} ${styles.bodyFont} ${isEntered ? styles.entered : ''}`}>
      <div className={styles.headerRow}>
        <div className={styles.headerLeft}>
          <div className={styles.headerTitleRow}>
            <Landmark size={16} color="var(--lm-accent)" />
            <h2 className={`${styles.headingFont} ${styles.headingText}`}>
              Best Lender Match
            </h2>
          </div>
          <span className={`${styles.subheading} ${styles.bodyFont}`}>
            Based on your current credit profile
          </span>
        </div>
        <span className={`${styles.matchStrengthPill} ${styles.bodyFont} ${getStrengthClass(match.matchStrength, styles)}`}>
          {getStrengthLabel(match.matchStrength)}
        </span>
      </div>

      <div className={`${styles.rule} ${styles.mt4}`} />

      <div className={`${styles.primaryBlock} ${styles.mt5}`}>
        <div className={styles.primaryHeader}>
          <div className={styles.lenderIconWrap}>
            <PrimaryIcon size={20} color="var(--lm-accent)" />
          </div>
          <div className={styles.primaryInfo}>
            <span className={`${styles.primaryName} ${styles.headingFont}`}>
              {match.primaryName}
            </span>
            <span className={`${styles.schemeBadge} ${styles.bodyFont}`}>
              <Tag size={11} />
              {match.schemeOrProduct}
            </span>
          </div>
        </div>
        <p className={`${styles.primaryReason} ${styles.bodyFont}`}>
          {match.primaryReason}
        </p>
        <p className={`${styles.schemeNote} ${styles.bodyFont}`}>
          {match.schemeNote}
        </p>
      </div>

      {match.fraudCaution ? (
        <div className={`${styles.fraudCaution} ${styles.bodyFont}`}>
          <AlertTriangle size={14} color="var(--lm-red)" style={{ flexShrink: 0, marginTop: 2 }} />
          <span className={styles.fraudCautionText}>
            Some lenders may flag your transaction patterns during review. Disclosing your UPI activity history upfront can help avoid delays.
          </span>
        </div>
      ) : null}

      <div className={styles.mt6}>
        <span className={`${styles.sectionLabel} ${styles.bodyFont}`}>
          Other options to consider
        </span>
        <div className={`${styles.alternativesList} ${styles.mt4}`}>
          {match.alternatives.map((alt) => {
            const AltIcon = getLenderIcon(alt.type);
            return (
              <div key={`${alt.type}-${alt.name}`} className={styles.alternativeRow}>
                <AltIcon size={16} className={styles.altIcon} />
                <div className={styles.altContent}>
                  <span className={`${styles.altName} ${styles.bodyFont}`}>
                    {alt.name}
                  </span>
                  <span className={`${styles.altNote} ${styles.bodyFont}`}>
                    {alt.note}
                  </span>
                </div>
                <span className={`${styles.eligibilityPill} ${styles.bodyFont} ${getEligClass(alt.eligibility, styles)}`}>
                  {getEligLabel(alt.eligibility)}
                </span>
              </div>
            );
          })}
        </div>
      </div>

      <div className={`${styles.rule} ${styles.mt5}`} />

      <p className={`${styles.footer} ${styles.bodyFont} ${styles.mt4}`}>
        Lender matching is based on your current credit score, risk band, and fraud assessment. Actual eligibility is subject to each lender&apos;s own criteria.
      </p>
    </section>
  );
}
